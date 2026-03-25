"""Auto-Launcher — daily campaign analysis and auto-launch.

Analyzes campaigns at 23:00 MSK, launches best ones at 04:00 MSK.
Multi-tenant: iterates over all users with configured credentials.
"""

import asyncio
import zoneinfo
from datetime import datetime, timedelta
from loguru import logger

from app.services.fbtool_client import FbtoolClient, FbtoolCampaign, FbtoolAuthError
from app.services.keitaro_client import KeitaroClient
from app.services.database_service import DatabaseService
from app.services.telegram_notifier import TelegramNotifier

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

# CPC thresholds per relaunch (5-day window)
CPC_THRESHOLD_LAUNCH_1 = 0.50  # After 1st launch: relaunch if CPC ≤ $0.50
CPC_THRESHOLD_LAUNCH_2 = 0.25  # After 2nd launch: relaunch if CPC ≤ $0.25
LAUNCH_WINDOW_DAYS = 5  # Count launches in this window
ROI_WINDOW_DAYS = 7  # Check ROI over this period


class AutoLauncher:
    def __init__(self, db: DatabaseService):
        self.db = db  # admin DatabaseService (service_role)

    @staticmethod
    def classify_campaign(
        leads_7d: int,
        roi_7d: float,
        launch_count_5d: int,
        cpc: float,
        last_2_launches_failed: bool,
        settings: dict,
    ) -> str | None:
        """Pure classification logic. Returns 'new', 'proven', 'blacklist', or None.

        Rules:
        1. Proven: 7-day ROI positive + has leads → relaunch
           Exception: last 2 launches both had loss + 0 leads → skip
        2. 1 launch in 5 days + CPC ≤ $0.50 → relaunch
        3. 2 launches in 5 days + CPC ≤ $0.25 → relaunch
        4. Everything else → skip
        """
        min_roi = float(settings.get("min_roi_threshold", 0))

        # Rule 1: Proven — 7-day positive ROI
        if leads_7d > 0 and roi_7d > min_roi:
            if last_2_launches_failed:
                return None  # was good but recent launches failed → skip
            return "proven"

        # Rules 2-4: Testing — CPC-based progressive thresholds
        if launch_count_5d == 0:
            # Never auto-launched — treat as first test with CPC check
            if cpc <= CPC_THRESHOLD_LAUNCH_1:
                return "new"
            return None  # skip, don't blacklist

        if launch_count_5d == 1:
            if cpc <= CPC_THRESHOLD_LAUNCH_1:
                return "new"
            return "blacklist"

        if launch_count_5d == 2:
            if cpc <= CPC_THRESHOLD_LAUNCH_2:
                return "new"
            return "blacklist"

        # 3+ launches → blacklist
        return "blacklist"

    async def run_analysis(self) -> None:
        """Analyze campaigns for all users. Runs at 23:00 MSK."""
        all_users = self.db.get_all_user_settings()
        for user_settings in all_users:
            user_id = user_settings["user_id"]
            if not user_settings.get("fbtool_cookies"):
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            settings = user_db.get_auto_launch_settings()
            if not settings or not settings.get("is_enabled"):
                continue

            fbtool_account_ids = user_settings.get("fbtool_account_ids") or []
            if not fbtool_account_ids:
                continue

            fbtool = FbtoolClient(cookies=user_settings["fbtool_cookies"])
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
                await self._run_analysis_for_user(
                    fbtool, keitaro, user_db, notifier, settings, fbtool_account_ids,
                )
            except Exception as e:
                logger.error(f"Auto-launcher analysis failed for user {user_id}: {e}")
            finally:
                await fbtool.close()
                await keitaro.close()
                if notifier:
                    await notifier.close()

    async def _run_analysis_for_user(
        self,
        fbtool: FbtoolClient,
        keitaro: KeitaroClient,
        db: DatabaseService,
        notifier: TelegramNotifier | None,
        settings: dict,
        fbtool_account_ids: list[int],
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
            logger.info(
                f"Auto-launcher: now={now.isoformat()}, hour={now.hour}, "
                f"launch_hour={launch_hour}, launch_date={launch_date}"
            )

            # Clear old and stale pending queue entries
            db.clear_old_launch_queue(str(launch_date))
            db.clear_pending_queue()

            # 1. Get accounts and filter by token status
            fbtool_accounts = await fbtool.get_accounts()
            active_account_names = {}
            error_accounts = []
            for acc in fbtool_accounts:
                if acc.token_status == "Ошибка":
                    error_accounts.append(acc)
                else:
                    active_account_names[acc.name] = acc

            # 2. Get all campaigns from fbtool — use wide date range (7 days)
            # to include campaigns that had no spend today but were active recently
            today_str = now.strftime("%Y-%m-%d")
            wide_start = (now - timedelta(days=7)).strftime("%Y-%m-%d")

            all_fbtool_campaigns: list[FbtoolCampaign] = []
            for account_id in fbtool_account_ids:
                try:
                    # Fetch with 7-day range so CPC reflects real data, not just today
                    campaigns = await fbtool.get_campaigns(
                        account_id, today_str, date_from=wide_start,
                    )
                    all_fbtool_campaigns.extend(campaigns)
                except Exception as e:
                    logger.error(f"Failed to fetch campaigns for fbtool account {account_id}: {e}")

            # 3. Get Keitaro stats (7-day window for ROI)
            await keitaro.ensure_authenticated()

            # If analysis runs after midnight but before launch_hour,
            # "today" has almost no data — use yesterday as the end date
            if now.hour < launch_hour:
                effective_today = (now - timedelta(days=1)).date()
            else:
                effective_today = now.date()

            date_7d_from = (effective_today - timedelta(days=ROI_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")
            date_to = effective_today.strftime("%Y-%m-%d")

            stats_7d = await keitaro.get_all_campaign_stats_by_period(
                date_from=date_7d_from, date_to=date_to,
            )

            # Launch window date for counting recent launches
            launch_window_from = (effective_today - timedelta(days=LAUNCH_WINDOW_DAYS - 1)).strftime("%Y-%m-%d")

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
                f"Auto-launcher: {len(all_fbtool_campaigns)} fbtool campaigns, "
                f"{len(db_campaigns)} DB campaigns, "
                f"{len(stats_7d)} in stats_7d, "
                f"{len(blacklisted_ids)} blacklisted"
            )

            skipped_reasons: dict[str, int] = {
                "not_in_db": 0, "not_managed": 0, "blacklisted": 0,
                "active": 0, "error_account": 0, "no_keitaro_data": 0,
                "classify_none": 0,
            }

            for fc in all_fbtool_campaigns:
                db_camp = db_campaigns.get(fc.fb_campaign_id)
                if not db_camp:
                    # Auto-create campaign in DB if account is known
                    db_acc = db_account_by_name.get(fc.account_name)
                    if not db_acc:
                        skipped_reasons["not_in_db"] += 1
                        continue
                    db_camp = db.upsert_campaign({
                        "fb_account_id": db_acc["id"],
                        "fb_campaign_id": str(fc.fb_campaign_id),
                        "fb_campaign_name": fc.name,
                        "status": "active" if fc.effective_status == "ACTIVE" else "paused",
                        "current_budget": fc.daily_budget,
                    })
                    db_campaigns[fc.fb_campaign_id] = db_camp
                    logger.info(f"Auto-synced new campaign to DB: {fc.name} (fb_id={fc.fb_campaign_id})")

                # Skip non-managed
                if not db_camp.get("is_managed", True):
                    skipped_reasons["not_managed"] += 1
                    continue

                # Skip blacklisted
                if db_camp["id"] in blacklisted_ids:
                    skipped_reasons["blacklisted"] += 1
                    continue

                # Only stopped/paused campaigns
                if fc.effective_status == "ACTIVE":
                    skipped_reasons["active"] += 1
                    logger.debug(f"  skip active: {fc.name} (status={fc.effective_status})")
                    continue

                # Skip error accounts
                if fc.account_name not in active_account_names:
                    skipped_reasons["error_account"] += 1
                    logger.debug(f"  skip error_account: {fc.name} (account={fc.account_name})")
                    continue

                # Get launch count (5-day window) and CPC from fbtool
                launch_count_5d = db.count_campaign_launches_since(
                    db_camp["id"], launch_window_from,
                )
                cpc = (fc.spend / fc.link_clicks) if fc.link_clicks > 0 else 0

                # Get 7-day Keitaro data
                k7d = stats_7d.get(fc.fb_campaign_id, {"conversions": 0, "roi": 0, "cost": 0})

                # Must have Keitaro data in 7-day window
                if fc.fb_campaign_id not in stats_7d:
                    skipped_reasons["no_keitaro_data"] += 1
                    logger.debug(f"  skip no_keitaro: {fc.name} (fb_id={fc.fb_campaign_id})")
                    continue

                # Check if last 2 launches both failed (loss + 0 leads)
                last_2_launches_failed = False
                if launch_count_5d >= 2:
                    last_launches = db.get_last_launches(db_camp["id"], limit=2)
                    if len(last_launches) >= 2:
                        last_2_launches_failed = all(
                            (l.get("analysis_data") or {}).get("leads_7d", 0) == 0
                            and (l.get("analysis_data") or {}).get("roi_7d", 0) <= 0
                            for l in last_launches
                        )

                launch_type = self.classify_campaign(
                    leads_7d=k7d["conversions"],
                    roi_7d=k7d["roi"],
                    launch_count_5d=launch_count_5d,
                    cpc=cpc,
                    last_2_launches_failed=last_2_launches_failed,
                    settings=settings,
                )

                logger.debug(
                    f"  classify: {fc.name} → {launch_type} "
                    f"(launches_5d={launch_count_5d}, cpc=${cpc:.2f}, "
                    f"last2_failed={last_2_launches_failed}, "
                    f"spend_7d={k7d['cost']}, leads_7d={k7d['conversions']}, roi_7d={k7d['roi']})"
                )

                if launch_type is None:
                    skipped_reasons["classify_none"] += 1
                    continue

                if launch_type == "blacklist":
                    db.add_to_blacklist({
                        "campaign_id": db_camp["id"],
                        "fb_campaign_id": fc.fb_campaign_id,
                        "fb_campaign_name": fc.name,
                        "reason": f"cpc_too_high_{launch_count_5d}launches",
                    })
                    blacklisted_count += 1
                    continue

                queue_items.append({
                    "campaign_id": db_camp["id"],
                    "fb_campaign_id": fc.fb_campaign_id,
                    "fbtool_account_id": fc.fbtool_account_id,
                    "fb_campaign_name": fc.name,
                    "fb_account_id": db_camp["fb_account_id"],
                    "launch_type": launch_type,
                    "target_budget": float(settings.get("starting_budget", 30)),
                    "analysis_data": {
                        "roi_7d": k7d["roi"],
                        "leads_7d": k7d["conversions"],
                        "spend_7d": k7d["cost"],
                        "cpc": round(cpc, 2),
                        "launch_count_5d": launch_count_5d,
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

        except FbtoolAuthError:
            logger.error("Auto-launcher analysis: Fbtool session expired")
            if notifier:
                await notifier.send(
                    "⚠️ Auto-Launcher: Fbtool сессия истекла! Анализ не выполнен."
                )

    async def run_launch(self) -> None:
        """Launch queued campaigns for all users. Runs at 04:00 MSK."""
        all_users = self.db.get_all_user_settings()
        for user_settings in all_users:
            user_id = user_settings["user_id"]
            if not user_settings.get("fbtool_cookies"):
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            settings = user_db.get_auto_launch_settings()
            if not settings or not settings.get("is_enabled"):
                continue

            fbtool = FbtoolClient(cookies=user_settings["fbtool_cookies"])
            notifier = None
            if user_settings.get("telegram_bot_token") and user_settings.get("telegram_chat_id"):
                notifier = TelegramNotifier(
                    bot_token=user_settings["telegram_bot_token"],
                    chat_id=user_settings["telegram_chat_id"],
                )

            fbtool_account_ids = user_settings.get("fbtool_account_ids") or []

            try:
                await self._run_launch_for_user(fbtool, user_db, notifier, fbtool_account_ids)
            except Exception as e:
                logger.error(f"Auto-launcher launch failed for user {user_id}: {e}")
            finally:
                await fbtool.close()
                if notifier:
                    await notifier.close()

    async def _run_launch_for_user(
        self,
        fbtool: FbtoolClient,
        db: DatabaseService,
        notifier: TelegramNotifier | None,
        fbtool_account_ids: list[int],
    ) -> None:
        """Launch queued campaigns for a single user."""
        try:
            now = datetime.now(MOSCOW_TZ)
            today = now.strftime("%Y-%m-%d")

            queue = db.get_launch_queue(launch_date=today, status="pending")
            logger.info(f"Auto-launcher launch: now={now.isoformat()}, looking for launch_date={today}")
            if not queue:
                logger.info("Auto-launcher: no campaigns to launch today")
                return

            # Fresh fbtool data for current status + account check
            all_fbtool_campaigns: list[FbtoolCampaign] = []
            for account_id in fbtool_account_ids:
                try:
                    campaigns = await fbtool.get_campaigns(account_id, today)
                    all_fbtool_campaigns.extend(campaigns)
                except Exception as e:
                    logger.error(f"Failed to fetch campaigns for fbtool account {account_id}: {e}")
            fbtool_by_fb_id = {fc.fb_campaign_id: fc for fc in all_fbtool_campaigns}

            fbtool_accounts = await fbtool.get_accounts()
            error_account_names = {
                acc.name for acc in fbtool_accounts
                if acc.token_status == "Ошибка"
            }

            launched = 0
            skipped = 0
            failed = 0

            for item in queue:
                try:
                    fc = fbtool_by_fb_id.get(item["fb_campaign_id"])
                    if not fc:
                        db.update_launch_queue_item(item["id"], {
                            "status": "failed",
                            "error_message": "Campaign not found in fbtool",
                        })
                        failed += 1
                        continue

                    # Skip if account has error
                    if fc.account_name in error_account_names:
                        db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                            "error_message": f"Account {fc.account_name} in error state",
                        })
                        skipped += 1
                        continue

                    # Skip if already active
                    if fc.effective_status == "ACTIVE":
                        db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                        })
                        skipped += 1
                        continue

                    # Determine fbtool_account_id for this campaign
                    campaign_fbtool_account_id = (
                        item.get("fbtool_account_id") or fc.fbtool_account_id
                    )

                    # Set budget first, then resume (with retry)
                    target_budget = float(item.get("target_budget", 30))
                    budget_set = False
                    resumed = False

                    # Retry set_budget up to 3 attempts (1 + 2 retries)
                    for attempt in range(3):
                        try:
                            await fbtool.set_budget(
                                campaign_fbtool_account_id, fc.fb_campaign_id, target_budget,
                            )
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

                    # Retry start_campaign up to 3 attempts (1 + 2 retries)
                    for attempt in range(3):
                        try:
                            await fbtool.start_campaign(
                                campaign_fbtool_account_id, fc.fb_campaign_id,
                            )
                            resumed = True
                            break
                        except Exception as e:
                            logger.warning(
                                f"start_campaign attempt {attempt + 1}/3 failed for "
                                f"{item['fb_campaign_name']}: {e}"
                            )
                            if attempt < 2:
                                await asyncio.sleep(2)

                    if not resumed:
                        # Budget was set but resume failed — log partial state
                        logger.error(
                            f"PARTIAL STATE: budget set to ${target_budget} but start "
                            f"failed for {item['fb_campaign_name']} (fb_id={fc.fb_campaign_id})"
                        )
                        db.update_launch_queue_item(item["id"], {
                            "status": "failed",
                            "error_message": (
                                f"Partial state: budget set to ${target_budget} "
                                f"but start_campaign failed after 3 attempts"
                            ),
                        })
                        try:
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
                        except Exception as log_err:
                            logger.warning(f"Failed to log partial auto_launch action: {log_err}")
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

                    # Log action (non-critical — don't fail launch on log error)
                    try:
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
                    except Exception as log_err:
                        logger.warning(f"Failed to log auto_launch action: {log_err}")

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
                    f"\U0001f680 Auto-Launcher: запуск завершён\n\n"
                    f"\u2705 Запущено: {launched}\n"
                    f"\u23ed Пропущено: {skipped}\n"
                    f"\u274c Ошибок: {failed}"
                )

            logger.info(f"Auto-launcher: {launched} launched, {skipped} skipped, {failed} failed")

        except FbtoolAuthError:
            logger.error("Auto-launcher launch: Fbtool session expired")
            if notifier:
                await notifier.send(
                    "⚠️ Auto-Launcher: Fbtool сессия истекла! Запуск не выполнен."
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

        lines = [f"\U0001f4cb Auto-Launcher: план на {launch_date}\n"]

        if new_items:
            lines.append(f"\n\U0001f195 Тест (CPC): {len(new_items)}")
            for item in new_items[:10]:
                ad = item["analysis_data"]
                launch_num = ad.get("launch_count_5d", 0) + 1
                cpc_str = f"${ad.get('cpc', 0):.2f}" if ad.get("cpc") is not None else "n/a"
                lines.append(
                    f"  \u2022 {item['fb_campaign_name']} "
                    f"(запуск #{launch_num}, CPC: {cpc_str})"
                )

        if proven_items:
            lines.append(f"\n\u2705 Проверенные (7д ROI+): {len(proven_items)}")
            for item in proven_items[:10]:
                ad = item["analysis_data"]
                lines.append(
                    f"  \u2022 {item['fb_campaign_name']} "
                    f"(ROI: {ad.get('roi_7d', 0):.0f}%, leads: {ad.get('leads_7d', 0)})"
                )

        if error_accounts:
            lines.append(f"\n\u26a0\ufe0f Аккаунты с ошибкой: {len(error_accounts)}")
            for acc in error_accounts[:5]:
                lines.append(f"  \u2022 {acc.name}: {acc.token_status}")

        if blacklisted_count:
            lines.append(f"\n\U0001f6ab Добавлено в чёрный список: {blacklisted_count}")

        if queue_items:
            budget = queue_items[0]["target_budget"]
            lines.append(f"\nБюджет: ${budget:.0f} | Запуск: 04:00 MSK")

        if not queue_items:
            lines.append("\nНет кампаний для запуска.")

        await notifier.send("\n".join(lines))
