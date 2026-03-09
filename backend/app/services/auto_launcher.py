"""Auto-Launcher — daily campaign analysis and auto-launch.

Analyzes campaigns at 23:00 MSK, launches best ones at 04:00 MSK.
"""

import zoneinfo
from datetime import datetime, timedelta
from loguru import logger

from app.services.panel_client import PanelClient, TokenExpiredError
from app.services.keitaro_client import KeitaroClient
from app.services.database_service import DatabaseService
from app.services.telegram_notifier import TelegramNotifier

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

# Threshold: if spend_7d / spend_2d < this ratio, campaign is "new"
NEW_CAMPAIGN_SPEND_RATIO = 1.5


class AutoLauncher:
    def __init__(
        self,
        panel: PanelClient,
        keitaro: KeitaroClient,
        db: DatabaseService,
        notifier: TelegramNotifier | None = None,
    ):
        self.panel = panel
        self.keitaro = keitaro
        self.db = db
        self.notifier = notifier

    @staticmethod
    def classify_campaign(
        spend_2d: float,
        spend_7d: float,
        leads_2d: int,
        roi_2d: float,
        settings: dict,
    ) -> str | None:
        """Pure classification logic. Returns 'new', 'proven', 'blacklist', or None."""
        min_roi = float(settings.get("min_roi_threshold", 0))

        # No activity at all
        if spend_2d == 0:
            return None

        # Determine if campaign is new (1-2 days) or established
        is_new = spend_7d <= 0 or (spend_7d / spend_2d) < NEW_CAMPAIGN_SPEND_RATIO

        if is_new:
            # New campaign with leads and positive ROI → proven
            if leads_2d > 0 and roi_2d > min_roi:
                return "proven"
            # New campaign, no leads yet → give another day
            if leads_2d == 0:
                return "new"
            # New campaign, has leads but bad ROI
            return None

        # Established campaign
        if leads_2d == 0:
            return "blacklist"
        if leads_2d > 0 and roi_2d > min_roi:
            return "proven"
        # Has leads but negative/low ROI → skip, don't blacklist
        return None

    async def run_analysis(self) -> None:
        """Analyze campaigns and build launch queue. Runs at 23:00 MSK."""
        settings = self.db.get_auto_launch_settings()
        if not settings or not settings.get("is_enabled"):
            logger.info("Auto-launcher disabled, skipping analysis")
            return

        try:
            now = datetime.now(MOSCOW_TZ)
            tomorrow = (now + timedelta(days=1)).date()

            # Clear old queue entries
            self.db.clear_old_launch_queue(str(tomorrow))

            # 1. Get accounts and filter ERROR/CHECKPOINT
            today_str = now.strftime("%Y-%m-%d")
            accounts = await self.panel.get_accounts(
                start_date=today_str, end_date=today_str,
            )
            active_account_names = {}
            error_accounts = []
            for acc in accounts:
                if acc.status in ("ERROR", "CHECKPOINT"):
                    error_accounts.append(acc)
                else:
                    active_account_names[acc.name] = acc

            # 2. Get all campaigns from Panel
            panel_campaigns = await self.panel.get_all_campaigns(
                start_date=today_str, end_date=today_str, with_spent=True,
            )

            # 3. Get Keitaro stats: 2-day and 7-day
            await self.keitaro.ensure_authenticated()

            date_2d_from = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            date_7d_from = (now - timedelta(days=6)).strftime("%Y-%m-%d")
            date_to = now.strftime("%Y-%m-%d")

            stats_2d = await self.keitaro.get_all_campaign_stats_by_period(
                date_from=date_2d_from, date_to=date_to,
            )
            stats_7d = await self.keitaro.get_all_campaign_stats_by_period(
                date_from=date_7d_from, date_to=date_to,
            )

            # 4. Get blacklist and DB campaigns
            blacklisted_ids = self.db.get_blacklisted_campaign_ids()
            db_campaigns_list = self.db.get_campaigns()
            db_campaigns = {c["fb_campaign_id"]: c for c in db_campaigns_list}

            # 5. Classify each campaign
            queue_items = []
            blacklisted_count = 0

            for pc in panel_campaigns:
                db_camp = db_campaigns.get(pc.campaign_id)
                if not db_camp:
                    continue

                # Skip non-managed
                if not db_camp.get("is_managed", True):
                    continue

                # Skip blacklisted
                if db_camp["id"] in blacklisted_ids:
                    continue

                # Only stopped/paused campaigns
                if pc.effective_status == "ACTIVE":
                    continue

                # Skip error accounts
                if pc.account_name not in active_account_names:
                    continue

                # Get Keitaro data
                k2d = stats_2d.get(pc.campaign_id, {"conversions": 0, "roi": 0, "cost": 0})
                k7d = stats_7d.get(pc.campaign_id, {"conversions": 0, "roi": 0, "cost": 0})

                # Not in 2-day data → skip (recency filter)
                if k2d["cost"] == 0 and pc.campaign_id not in stats_2d:
                    continue

                launch_type = self.classify_campaign(
                    spend_2d=k2d["cost"],
                    spend_7d=k7d["cost"],
                    leads_2d=k2d["conversions"],
                    roi_2d=k2d["roi"],
                    settings=settings,
                )

                if launch_type == "blacklist":
                    self.db.add_to_blacklist({
                        "campaign_id": db_camp["id"],
                        "fb_campaign_id": pc.campaign_id,
                        "fb_campaign_name": pc.name,
                        "reason": "zero_leads_2d",
                    })
                    blacklisted_count += 1
                    continue

                if launch_type is None:
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
                        "spend_7d": k7d["cost"],
                    },
                    "status": "pending",
                    "launch_date": str(tomorrow),
                })

            # 6. Write queue to DB
            for item in queue_items:
                self.db.add_to_launch_queue(item)

            # 7. Send Telegram notification
            if self.notifier:
                await self._send_analysis_telegram(
                    queue_items, error_accounts, blacklisted_count, tomorrow,
                )

            logger.info(
                f"Auto-launcher analysis: {len(queue_items)} queued, "
                f"{blacklisted_count} blacklisted for {tomorrow}"
            )

        except TokenExpiredError:
            logger.error("Auto-launcher analysis: Panel JWT expired")
            if self.notifier:
                await self.notifier.send(
                    "⚠️ Auto-Launcher: Panel JWT истёк! Анализ не выполнен."
                )
        except Exception as e:
            logger.exception(f"Auto-launcher analysis failed: {e}")

    async def run_launch(self) -> None:
        """Launch queued campaigns. Runs at 04:00 MSK."""
        settings = self.db.get_auto_launch_settings()
        if not settings or not settings.get("is_enabled"):
            logger.info("Auto-launcher disabled, skipping launch")
            return

        try:
            now = datetime.now(MOSCOW_TZ)
            today = now.strftime("%Y-%m-%d")

            queue = self.db.get_launch_queue(launch_date=today, status="pending")
            if not queue:
                logger.info("Auto-launcher: no campaigns to launch today")
                return

            # Fresh Panel data for current status + account check
            panel_campaigns = await self.panel.get_all_campaigns(
                start_date=today, end_date=today,
            )
            panel_by_fb_id = {pc.campaign_id: pc for pc in panel_campaigns}

            accounts = await self.panel.get_accounts(
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
                        self.db.update_launch_queue_item(item["id"], {
                            "status": "failed",
                            "error_message": "Campaign not found in Panel",
                        })
                        failed += 1
                        continue

                    # Skip if account has error
                    if pc.account_name in error_account_names:
                        self.db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                            "error_message": f"Account {pc.account_name} in error state",
                        })
                        skipped += 1
                        continue

                    # Skip if already active
                    if pc.effective_status == "ACTIVE":
                        self.db.update_launch_queue_item(item["id"], {
                            "status": "skipped",
                        })
                        skipped += 1
                        continue

                    # Set budget first, then resume
                    target_budget = float(item.get("target_budget", 30))
                    await self.panel.set_budget(pc.internal_id, target_budget)
                    await self.panel.resume_campaign(pc.internal_id)

                    # Update queue
                    self.db.update_launch_queue_item(item["id"], {
                        "status": "launched",
                        "launched_at": datetime.now(MOSCOW_TZ).isoformat(),
                    })

                    # Update campaign in DB
                    self.db.update_campaign(item["campaign_id"], {
                        "status": "active",
                        "current_budget": target_budget,
                    })

                    # Log action
                    self.db.create_action_log({
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

                except Exception as e:
                    failed += 1
                    logger.error(f"Failed to launch {item['fb_campaign_name']}: {e}")
                    self.db.update_launch_queue_item(item["id"], {
                        "status": "failed",
                        "error_message": str(e)[:500],
                    })

            # Telegram report
            if self.notifier:
                await self.notifier.send(
                    f"🚀 Auto-Launcher: запуск завершён\n\n"
                    f"✅ Запущено: {launched}\n"
                    f"⏭ Пропущено: {skipped}\n"
                    f"❌ Ошибок: {failed}"
                )

            logger.info(f"Auto-launcher: {launched} launched, {skipped} skipped, {failed} failed")

        except TokenExpiredError:
            logger.error("Auto-launcher launch: Panel JWT expired")
            if self.notifier:
                await self.notifier.send(
                    "⚠️ Auto-Launcher: Panel JWT истёк! Запуск не выполнен."
                )
        except Exception as e:
            logger.exception(f"Auto-launcher launch failed: {e}")

    async def _send_analysis_telegram(
        self,
        queue_items: list[dict],
        error_accounts: list,
        blacklisted_count: int,
        launch_date,
    ) -> None:
        new_items = [i for i in queue_items if i["launch_type"] == "new"]
        proven_items = [i for i in queue_items if i["launch_type"] == "proven"]

        lines = [f"📋 Auto-Launcher: план на {launch_date}\n"]

        if new_items:
            lines.append(f"\n🆕 Новые (тест): {len(new_items)}")
            for item in new_items[:10]:
                lines.append(f"  • {item['fb_campaign_name']}")

        if proven_items:
            lines.append(f"\n✅ Проверенные: {len(proven_items)}")
            for item in proven_items[:10]:
                ad = item["analysis_data"]
                lines.append(
                    f"  • {item['fb_campaign_name']} "
                    f"(ROI: {ad.get('roi_2d', 0):.0f}%, leads: {ad.get('leads_2d', 0)})"
                )

        if error_accounts:
            lines.append(f"\n⚠️ Аккаунты с ошибкой: {len(error_accounts)}")
            for acc in error_accounts[:5]:
                lines.append(f"  • {acc.name}: {acc.status}")

        if blacklisted_count:
            lines.append(f"\n🚫 Добавлено в чёрный список: {blacklisted_count}")

        if queue_items:
            budget = queue_items[0]["target_budget"]
            lines.append(f"\nБюджет: ${budget:.0f} | Запуск: 04:00 MSK")

        if not queue_items:
            lines.append("\nНет кампаний для запуска.")

        await self.notifier.send("\n".join(lines))
