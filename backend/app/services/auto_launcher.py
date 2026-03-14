"""Auto-Launcher — daily campaign analysis and auto-launch.

Analyzes campaigns at 23:00 MSK, launches best ones at 04:00 MSK.
Multi-tenant: iterates over all users with configured credentials.
"""

import asyncio
import re
import zoneinfo
from datetime import datetime, timedelta
from loguru import logger

from app.services.panel_client import PanelClient, TokenExpiredError
from app.services.keitaro_client import KeitaroClient
from app.services.database_service import DatabaseService
from app.services.telegram_notifier import TelegramNotifier

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

# Campaign created within this many days is considered "new"
NEW_CAMPAIGN_DAYS = 6
# Max CPC ($/click) — campaigns with higher CPC are not relaunched
MAX_CPC_FOR_RELAUNCH = 0.70
# Max times a new campaign can be auto-launched (0 or 1 → ok, 2+ → skip)
MAX_LAUNCHES = 2

# Pattern to extract date from campaign name like "13.03 v1 ..." or "13. 03 v1 ..."
_NAME_DATE_RE = re.compile(r"^(\d{1,2})\.\s*(\d{2})\b")


class AutoLauncher:
    def __init__(self, db: DatabaseService):
        self.db = db  # admin DatabaseService (service_role)

    @staticmethod
    def classify_campaign(
        leads_2d: int,
        roi_2d: float,
        is_new: bool,
        settings: dict,
    ) -> str | None:
        """Pure classification logic. Returns 'new', 'proven', 'blacklist', or None."""
        min_roi = float(settings.get("min_roi_threshold", 0))

        if is_new:
            # New campaign with leads and positive ROI → proven
            if leads_2d > 0 and roi_2d > min_roi:
                return "proven"
            # New campaign — always relaunch for testing
            # (ladder rules will stop it if spend/CPL is too high)
            return "new"

        # Established campaign
        if leads_2d == 0:
            return "blacklist"
        if leads_2d > 0 and roi_2d > min_roi:
            return "proven"
        # Has leads but negative/low ROI → skip, don't blacklist
        return None

    async def run_analysis(self) -> None:
        """Analyze campaigns for all users. Runs at 23:00 MSK."""
        all_users = self.db.get_all_user_settings()
        for user_settings in all_users:
            user_id = user_settings["user_id"]
            if not user_settings.get("panel_jwt"):
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            settings = user_db.get_auto_launch_settings()
            if not settings or not settings.get("is_enabled"):
                continue

            panel = PanelClient(
                base_url=user_settings.get("panel_api_url") or None,
                jwt_token=user_settings["panel_jwt"],
            )
            keitaro = KeitaroClient(
                base_url=user_settings.get("keitaro_url") or None,
                login=user_settings.get("keitaro_login") or None,
                password=user_settings.get("keitaro_password") or None,
            )
            notifier = None
            if user_settings.get("telegram_bot_token") and user_settings.get("telegram_chat_id"):
                notifier = TelegramNotifier(
                    bot_token=user_settings["telegram_bot_token"],
                    chat_id=user_settings["telegram_chat_id"],
                )

            try:
                await self._run_analysis_for_user(panel, keitaro, user_db, notifier, settings)
            except Exception as e:
                logger.error(f"Auto-launcher analysis failed for user {user_id}: {e}")
            finally:
                await panel.close()
                await keitaro.close()
                if notifier:
                    await notifier.close()

    async def _run_analysis_for_user(
        self,
        panel: PanelClient,
        keitaro: KeitaroClient,
        db: DatabaseService,
        notifier: TelegramNotifier | None,
        settings: dict,
    ) -> None:
        """Analyze campaigns and build launch queue for a single user."""
        try:
            now = datetime.now(MOSCOW_TZ)
            launch_hour = int(settings.get("launch_hour", 4))

            # If current time is before launch hour → launch today at launch_hour
            # If current time is after launch hour → launch tomorrow at launch_hour
            if now.hour < launch_hour:
                launch_date = now.date()
            else:
                launch_date = (now + timedelta(days=1)).date()

            # Clear old queue entries
            db.clear_old_launch_queue(str(launch_date))

            # 1. Get accounts and filter ERROR/CHECKPOINT
            today_str = now.strftime("%Y-%m-%d")
            accounts = await panel.get_accounts(
                start_date=today_str, end_date=today_str,
            )
            active_account_names = {}
            error_accounts = []
            for acc in accounts:
                if acc.status in ("ERROR", "CHECKPOINT"):
                    error_accounts.append(acc)
                else:
                    active_account_names[acc.name] = acc

            # 2. Get all campaigns from Panel — use wide date range to include
            # campaigns that had no spend today but were active recently
            wide_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
            panel_campaigns = await panel.get_all_campaigns(
                start_date=wide_start, end_date=today_str,
            )

            # 3. Get Keitaro stats: 2-day and 7-day
            await keitaro.ensure_authenticated()

            # If analysis runs after midnight but before launch_hour,
            # "today" has almost no data — use yesterday as the end date
            if now.hour < launch_hour:
                effective_today = (now - timedelta(days=1)).date()
            else:
                effective_today = now.date()

            date_2d_from = (effective_today - timedelta(days=1)).strftime("%Y-%m-%d")
            date_to = effective_today.strftime("%Y-%m-%d")

            stats_2d = await keitaro.get_all_campaign_stats_by_period(
                date_from=date_2d_from, date_to=date_to,
            )

            # 4. Get blacklist, DB campaigns, and DB accounts (for auto-sync)
            blacklisted_ids = db.get_blacklisted_campaign_ids()
            db_campaigns_list = db.get_campaigns()
            db_campaigns = {c["fb_campaign_id"]: c for c in db_campaigns_list}

            db_accounts = db.get_accounts()
            db_account_by_name = {a["name"]: a for a in db_accounts}

            # 5. Classify each campaign
            queue_items = []
            blacklisted_count = 0

            logger.info(
                f"Auto-launcher: {len(panel_campaigns)} panel campaigns, "
                f"{len(db_campaigns)} DB campaigns, "
                f"{len(stats_2d)} in stats_2d, "
                f"{len(blacklisted_ids)} blacklisted"
            )

            skipped_reasons: dict[str, int] = {
                "not_in_db": 0, "not_managed": 0, "blacklisted": 0,
                "active": 0, "error_account": 0, "no_keitaro_data": 0,
                "classify_none": 0,
            }

            for pc in panel_campaigns:
                db_camp = db_campaigns.get(pc.campaign_id)
                if not db_camp:
                    # Auto-create campaign in DB if account is known
                    db_acc = db_account_by_name.get(pc.account_name)
                    if not db_acc:
                        skipped_reasons["not_in_db"] += 1
                        continue
                    db_camp = db.upsert_campaign({
                        "fb_account_id": db_acc["id"],
                        "fb_campaign_id": str(pc.campaign_id),
                        "panel_campaign_id": pc.internal_id,
                        "fb_campaign_name": pc.name,
                        "status": "active" if pc.effective_status == "ACTIVE" else "paused",
                        "current_budget": pc.daily_budget,
                    })
                    db_campaigns[pc.campaign_id] = db_camp
                    logger.info(f"Auto-synced new campaign to DB: {pc.name} (fb_id={pc.campaign_id})")

                # Skip non-managed
                if not db_camp.get("is_managed", True):
                    skipped_reasons["not_managed"] += 1
                    continue

                # Skip blacklisted
                if db_camp["id"] in blacklisted_ids:
                    skipped_reasons["blacklisted"] += 1
                    continue

                # Only stopped/paused campaigns
                if pc.effective_status == "ACTIVE":
                    skipped_reasons["active"] += 1
                    continue

                # Skip error accounts
                if pc.account_name not in active_account_names:
                    skipped_reasons["error_account"] += 1
                    logger.debug(f"  skip error_account: {pc.name} (account={pc.account_name})")
                    continue

                # Determine if campaign is "new" by date in name (e.g. "13.03")
                m = _NAME_DATE_RE.match(pc.name)
                if m:
                    day, month = int(m.group(1)), int(m.group(2))
                    try:
                        campaign_date = now.replace(
                            month=month, day=day, hour=0, minute=0, second=0, microsecond=0,
                        )
                        age_days = (now - campaign_date).days
                    except ValueError:
                        age_days = 9999
                else:
                    age_days = 9999
                is_new = 0 <= age_days < NEW_CAMPAIGN_DAYS

                # For new campaigns: check launch count and CPC limits
                if is_new:
                    launch_count = db.count_campaign_launches(db_camp["id"])
                    cpc = (pc.spend / pc.link_clicks) if pc.link_clicks > 0 else 0
                    if launch_count >= MAX_LAUNCHES:
                        skipped_reasons["classify_none"] += 1
                        logger.debug(
                            f"  skip max_launches: {pc.name} "
                            f"(launched {launch_count}x, max {MAX_LAUNCHES})"
                        )
                        continue
                    if cpc > MAX_CPC_FOR_RELAUNCH:
                        skipped_reasons["classify_none"] += 1
                        logger.debug(
                            f"  skip high_cpc: {pc.name} "
                            f"(cpc=${cpc:.2f} > ${MAX_CPC_FOR_RELAUNCH})"
                        )
                        continue

                # Get Keitaro data
                k2d = stats_2d.get(pc.campaign_id, {"conversions": 0, "roi": 0, "cost": 0})

                # Not in 2-day data → skip (recency filter), but allow new campaigns
                if not is_new and k2d["cost"] == 0 and pc.campaign_id not in stats_2d:
                    skipped_reasons["no_keitaro_data"] += 1
                    logger.debug(f"  skip no_keitaro: {pc.name} (fb_id={pc.campaign_id})")
                    continue

                launch_type = self.classify_campaign(
                    leads_2d=k2d["conversions"],
                    roi_2d=k2d["roi"],
                    is_new=is_new,
                    settings=settings,
                )

                logger.debug(
                    f"  classify: {pc.name} → {launch_type} "
                    f"(is_new={is_new}, age={age_days}d, "
                    f"spend_2d={k2d['cost']}, leads_2d={k2d['conversions']}, roi_2d={k2d['roi']})"
                )

                if launch_type is None:
                    skipped_reasons["classify_none"] += 1
                    continue

                if launch_type == "blacklist":
                    db.add_to_blacklist({
                        "campaign_id": db_camp["id"],
                        "fb_campaign_id": pc.campaign_id,
                        "fb_campaign_name": pc.name,
                        "reason": "zero_leads_2d",
                    })
                    blacklisted_count += 1
                    continue

                queue_items.append({
                    "campaign_id": db_camp["id"],
                    "fb_campaign_id": pc.campaign_id,
                    "panel_campaign_id": pc.internal_id,
                    "fb_campaign_name": pc.name,
                    "fb_account_id": db_camp["fb_account_id"],
                    "launch_type": launch_type,
                    "target_budget": float(settings.get("starting_budget", 30)),
                    "analysis_data": {
                        "roi_2d": k2d["roi"],
                        "leads_2d": k2d["conversions"],
                        "spend_2d": k2d["cost"],
                    },
                    "status": "pending",
                    "launch_date": str(launch_date),
                })

            logger.info(f"Auto-launcher skip reasons: {skipped_reasons}")

            # 6. Write queue to DB
            for item in queue_items:
                db.add_to_launch_queue(item)

            # 7. Send Telegram notification
            if notifier:
                await self._send_analysis_telegram(
                    notifier, queue_items, error_accounts, blacklisted_count, launch_date,
                )

            logger.info(
                f"Auto-launcher analysis: {len(queue_items)} queued, "
                f"{blacklisted_count} blacklisted for {launch_date}"
            )

        except TokenExpiredError:
            logger.error("Auto-launcher analysis: Panel JWT expired")
            if notifier:
                await notifier.send(
                    "\u26a0\ufe0f Auto-Launcher: Panel JWT \u0438\u0441\u0442\u0451\u043a! \u0410\u043d\u0430\u043b\u0438\u0437 \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d."
                )

    async def run_launch(self) -> None:
        """Launch queued campaigns for all users. Runs at 04:00 MSK."""
        all_users = self.db.get_all_user_settings()
        for user_settings in all_users:
            user_id = user_settings["user_id"]
            if not user_settings.get("panel_jwt"):
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            settings = user_db.get_auto_launch_settings()
            if not settings or not settings.get("is_enabled"):
                continue

            panel = PanelClient(
                base_url=user_settings.get("panel_api_url") or None,
                jwt_token=user_settings["panel_jwt"],
            )
            notifier = None
            if user_settings.get("telegram_bot_token") and user_settings.get("telegram_chat_id"):
                notifier = TelegramNotifier(
                    bot_token=user_settings["telegram_bot_token"],
                    chat_id=user_settings["telegram_chat_id"],
                )

            try:
                await self._run_launch_for_user(panel, user_db, notifier)
            except Exception as e:
                logger.error(f"Auto-launcher launch failed for user {user_id}: {e}")
            finally:
                await panel.close()
                if notifier:
                    await notifier.close()

    async def _run_launch_for_user(
        self,
        panel: PanelClient,
        db: DatabaseService,
        notifier: TelegramNotifier | None,
    ) -> None:
        """Launch queued campaigns for a single user."""
        try:
            now = datetime.now(MOSCOW_TZ)
            today = now.strftime("%Y-%m-%d")

            queue = db.get_launch_queue(launch_date=today, status="pending")
            if not queue:
                logger.info("Auto-launcher: no campaigns to launch today")
                return

            # Fresh Panel data for current status + account check
            panel_campaigns = await panel.get_all_campaigns(
                start_date=today, end_date=today,
            )
            panel_by_fb_id = {pc.campaign_id: pc for pc in panel_campaigns}

            accounts = await panel.get_accounts(
                start_date=today, end_date=today,
            )
            error_account_names = {
                acc.name for acc in accounts
                if acc.status in ("ERROR", "CHECKPOINT")
            }

            launched = 0
            skipped = 0
            failed = 0

            for item in queue:
                try:
                    pc = panel_by_fb_id.get(item["fb_campaign_id"])
                    if not pc:
                        db.update_launch_queue_item(item["id"], {
                            "status": "failed",
                            "error_message": "Campaign not found in Panel",
                        })
                        failed += 1
                        continue

                    # Skip if account has error
                    if pc.account_name in error_account_names:
                        db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                            "error_message": f"Account {pc.account_name} in error state",
                        })
                        skipped += 1
                        continue

                    # Skip if already active
                    if pc.effective_status == "ACTIVE":
                        db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                        })
                        skipped += 1
                        continue

                    # Set budget first, then resume (with retry)
                    target_budget = float(item.get("target_budget", 30))
                    budget_set = False
                    resumed = False

                    # Retry set_budget up to 3 attempts (1 + 2 retries)
                    for attempt in range(3):
                        try:
                            await panel.set_budget(pc.internal_id, target_budget)
                            budget_set = True
                            break
                        except Exception as e:
                            logger.warning(
                                f"set_budget attempt {attempt + 1}/3 failed for "
                                f"{item['fb_campaign_name']}: {e}"
                            )
                            if attempt < 2:
                                await asyncio.sleep(2)

                    if not budget_set:
                        raise RuntimeError(
                            f"set_budget failed after 3 attempts for {item['fb_campaign_name']}"
                        )

                    # Retry resume_campaign up to 3 attempts (1 + 2 retries)
                    for attempt in range(3):
                        try:
                            await panel.resume_campaign(pc.internal_id)
                            resumed = True
                            break
                        except Exception as e:
                            logger.warning(
                                f"resume_campaign attempt {attempt + 1}/3 failed for "
                                f"{item['fb_campaign_name']}: {e}"
                            )
                            if attempt < 2:
                                await asyncio.sleep(2)

                    if not resumed:
                        # Budget was set but resume failed — log partial state
                        logger.error(
                            f"PARTIAL STATE: budget set to ${target_budget} but resume "
                            f"failed for {item['fb_campaign_name']} (panel_id={pc.internal_id})"
                        )
                        db.update_launch_queue_item(item["id"], {
                            "status": "failed",
                            "error_message": (
                                f"Partial state: budget set to ${target_budget} "
                                f"but resume_campaign failed after 3 attempts"
                            ),
                        })
                        db.create_action_log({
                            "campaign_id": str(item["campaign_id"]),
                            "fb_account_id": str(item["fb_account_id"]),
                            "action_type": "auto_launch",
                            "details": {
                                "launch_type": item["launch_type"],
                                "target_budget": target_budget,
                                "partial_state": True,
                                "budget_set": True,
                                "resumed": False,
                                "analysis_data": item.get("analysis_data", {}),
                            },
                            "success": False,
                        })
                        failed += 1
                        continue

                    # Update queue
                    db.update_launch_queue_item(item["id"], {
                        "status": "launched",
                        "launched_at": datetime.now(MOSCOW_TZ).isoformat(),
                    })

                    # Update campaign in DB
                    db.update_campaign(item["campaign_id"], {
                        "status": "active",
                        "current_budget": target_budget,
                    })

                    # Log action
                    db.create_action_log({
                        "campaign_id": str(item["campaign_id"]),
                        "fb_account_id": str(item["fb_account_id"]),
                        "action_type": "auto_launch",
                        "details": {
                            "launch_type": item["launch_type"],
                            "target_budget": target_budget,
                            "analysis_data": item.get("analysis_data", {}),
                        },
                        "success": True,
                    })

                    launched += 1
                    logger.info(f"Auto-launched: {item['fb_campaign_name']} (${target_budget})")

                    # Delay between launches to avoid FB rate limits
                    await asyncio.sleep(30)

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to launch {item['fb_campaign_name']}: {e}")
                    db.update_launch_queue_item(item["id"], {
                        "status": "failed",
                        "error_message": str(e)[:500],
                    })

            # Telegram report
            if notifier:
                await notifier.send(
                    f"\U0001f680 Auto-Launcher: \u0437\u0430\u043f\u0443\u0441\u043a \u0437\u0430\u0432\u0435\u0440\u0448\u0451\u043d\n\n"
                    f"\u2705 \u0417\u0430\u043f\u0443\u0449\u0435\u043d\u043e: {launched}\n"
                    f"\u23ed \u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e: {skipped}\n"
                    f"\u274c \u041e\u0448\u0438\u0431\u043e\u043a: {failed}"
                )

            logger.info(f"Auto-launcher: {launched} launched, {skipped} skipped, {failed} failed")

        except TokenExpiredError:
            logger.error("Auto-launcher launch: Panel JWT expired")
            if notifier:
                await notifier.send(
                    "\u26a0\ufe0f Auto-Launcher: Panel JWT \u0438\u0441\u0442\u0451\u043a! \u0417\u0430\u043f\u0443\u0441\u043a \u043d\u0435 \u0432\u044b\u043f\u043e\u043b\u043d\u0435\u043d."
                )

    async def _send_analysis_telegram(
        self,
        notifier: TelegramNotifier,
        queue_items: list[dict],
        error_accounts: list,
        blacklisted_count: int,
        launch_date,
    ) -> None:
        new_items = [i for i in queue_items if i["launch_type"] == "new"]
        proven_items = [i for i in queue_items if i["launch_type"] == "proven"]

        lines = [f"\U0001f4cb Auto-Launcher: \u043f\u043b\u0430\u043d \u043d\u0430 {launch_date}\n"]

        if new_items:
            lines.append(f"\n\U0001f195 \u041d\u043e\u0432\u044b\u0435 (\u0442\u0435\u0441\u0442): {len(new_items)}")
            for item in new_items[:10]:
                lines.append(f"  \u2022 {item['fb_campaign_name']}")

        if proven_items:
            lines.append(f"\n\u2705 \u041f\u0440\u043e\u0432\u0435\u0440\u0435\u043d\u043d\u044b\u0435: {len(proven_items)}")
            for item in proven_items[:10]:
                ad = item["analysis_data"]
                lines.append(
                    f"  \u2022 {item['fb_campaign_name']} "
                    f"(ROI: {ad.get('roi_2d', 0):.0f}%, leads: {ad.get('leads_2d', 0)})"
                )

        if error_accounts:
            lines.append(f"\n\u26a0\ufe0f \u0410\u043a\u043a\u0430\u0443\u043d\u0442\u044b \u0441 \u043e\u0448\u0438\u0431\u043a\u043e\u0439: {len(error_accounts)}")
            for acc in error_accounts[:5]:
                lines.append(f"  \u2022 {acc.name}: {acc.status}")

        if blacklisted_count:
            lines.append(f"\n\U0001f6ab \u0414\u043e\u0431\u0430\u0432\u043b\u0435\u043d\u043e \u0432 \u0447\u0451\u0440\u043d\u044b\u0439 \u0441\u043f\u0438\u0441\u043e\u043a: {blacklisted_count}")

        if queue_items:
            budget = queue_items[0]["target_budget"]
            lines.append(f"\n\u0411\u044e\u0434\u0436\u0435\u0442: ${budget:.0f} | \u0417\u0430\u043f\u0443\u0441\u043a: 04:00 MSK")

        if not queue_items:
            lines.append("\n\u041d\u0435\u0442 \u043a\u0430\u043c\u043f\u0430\u043d\u0438\u0439 \u0434\u043b\u044f \u0437\u0430\u043f\u0443\u0441\u043a\u0430.")

        await notifier.send("\n".join(lines))
