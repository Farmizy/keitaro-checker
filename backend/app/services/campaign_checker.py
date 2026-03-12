"""Orchestrator for the 10-minute campaign check cycle.

Multi-tenant: iterates over all users with configured settings,
creates per-user clients, runs checks independently.

Flow per user:
1. Fetch campaigns + spend from Panel API
2. Fetch conversions from Keitaro
3. Sync campaigns to DB
4. For each active campaign: evaluate rules → execute action → log
"""

import zoneinfo
from datetime import datetime, timezone

from loguru import logger

from app.services.panel_client import PanelClient, PanelCampaign, TokenExpiredError
from app.services.keitaro_client import KeitaroClient
from app.services.database_service import DatabaseService
from app.services.action_executor import ActionExecutor
from app.services.rule_engine import evaluate, parse_db_rules, CampaignState, ActionType
from app.services.telegram_notifier import TelegramNotifier

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")


class CampaignChecker:

    def __init__(self, db: DatabaseService):
        self.db = db  # admin DatabaseService (service_role)

    async def run_check(self):
        """Main check cycle — iterates over all configured users."""
        all_users = self.db.get_all_user_settings()
        logger.info(f"Starting check cycle for {len(all_users)} user(s)")

        for user_settings in all_users:
            user_id = user_settings["user_id"]

            # Skip users without Panel JWT (not configured)
            if not user_settings.get("panel_jwt"):
                logger.debug(f"User {user_id}: no panel_jwt — skipped")
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            panel = PanelClient(
                base_url=user_settings.get("panel_api_url") or None,
                jwt_token=user_settings["panel_jwt"],
            )
            keitaro = KeitaroClient(
                base_url=user_settings.get("keitaro_url") or None,
                login=user_settings.get("keitaro_login") or None,
                password=user_settings.get("keitaro_password") or None,
            )
            executor = ActionExecutor(panel=panel, db=user_db)

            notifier = None
            if user_settings.get("telegram_bot_token") and user_settings.get("telegram_chat_id"):
                notifier = TelegramNotifier(
                    bot_token=user_settings["telegram_bot_token"],
                    chat_id=user_settings["telegram_chat_id"],
                )

            try:
                await self._run_check_for_user(panel, keitaro, user_db, executor, notifier)
            except Exception as e:
                logger.error(f"Check failed for user {user_id}: {e}")
            finally:
                await panel.close()
                await keitaro.close()
                if notifier:
                    await notifier.close()

    async def _run_check_for_user(
        self,
        panel: PanelClient,
        keitaro: KeitaroClient,
        db: DatabaseService,
        executor: ActionExecutor,
        notifier: TelegramNotifier | None,
    ):
        """Run full check cycle for a single user."""
        run = db.create_check_run({
            "status": "running",
            "started_at": datetime.now(timezone.utc).isoformat(),
        })
        run_id = run["id"]

        campaigns_checked = 0
        actions_taken = 0
        errors_count = 0

        try:
            now = datetime.now(MOSCOW_TZ)
            today = now.strftime("%Y-%m-%d")

            # 1. Sync accounts from Panel every cycle
            logger.info("Syncing accounts from Panel...")
            await self._sync_accounts_from_panel(panel, db, today)
            db_accounts = db.get_active_accounts()
            logger.info(f"Got {len(db_accounts)} accounts from DB")

            # 2. Fetch campaigns from Panel API (with spend)
            logger.info("Fetching campaigns from Panel API...")
            panel_campaigns = await panel.get_all_campaigns(
                start_date=today,
                end_date=today,
                with_spent=True,
            )
            logger.info(f"Got {len(panel_campaigns)} campaigns from Panel")

            # 2b. Update accounts with real FB ad account IDs from campaign data
            self._update_account_fb_ids(db, panel_campaigns)

            # 3. Fetch conversions from Keitaro (grouped by campaign_id via sub_id_2)
            logger.info("Fetching conversions from Keitaro...")
            keitaro_conversions: dict[str, int] = {}
            keitaro_available = True
            try:
                await keitaro.ensure_authenticated()
                keitaro_conversions = await keitaro.get_all_conversions_by_campaign()
                logger.info(f"Got conversions for {len(keitaro_conversions)} campaign IDs from Keitaro")
            except Exception as e:
                keitaro_available = False
                logger.error(f"Keitaro fetch failed, using Panel leads as fallback: {e}")
                if notifier:
                    try:
                        await notifier.send(
                            "⚠️ <b>Keitaro недоступен</b>\n\n"
                            f"Ошибка: {e}\n"
                            "Проверка использует лиды из Panel API как fallback."
                        )
                    except Exception:
                        pass

            # 4. Build account mappings (prefer panel_account_id, fallback to name)
            account_by_panel_id = {
                acc["panel_account_id"]: acc
                for acc in db_accounts
                if acc.get("panel_account_id")
            }
            account_by_name = {acc["name"]: acc for acc in db_accounts}

            # 4b. Load user's rule set from DB
            rule_kwargs = {}
            rule_set = db.get_default_rule_set()
            if rule_set and rule_set.get("rule_steps"):
                rule_kwargs = parse_db_rules(rule_set["rule_steps"])
                logger.info(f"Loaded {len(rule_set['rule_steps'])} rule steps from DB")
            else:
                logger.info("No custom rules found, using defaults")

            # 5. Process each campaign
            for pc in panel_campaigns:
                try:
                    result = await self._process_campaign(
                        db, executor, notifier,
                        pc, account_by_panel_id, account_by_name,
                        keitaro_conversions, now, rule_kwargs,
                    )
                    if result == "checked":
                        campaigns_checked += 1
                    elif result == "action":
                        campaigns_checked += 1
                        actions_taken += 1
                except Exception as e:
                    errors_count += 1
                    logger.error(f"Error processing campaign {pc.campaign_id}: {e}")

            db.update_check_run(run_id, {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "campaigns_checked": campaigns_checked,
                "actions_taken": actions_taken,
                "errors_count": errors_count,
                "details": {"keitaro_available": keitaro_available},
            })

            logger.info(
                f"Check complete: {campaigns_checked} checked, "
                f"{actions_taken} actions, {errors_count} errors"
            )

        except TokenExpiredError as e:
            logger.error(f"Panel JWT expired, skipping check cycle: {e}")
            db.update_check_run(run_id, {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "campaigns_checked": campaigns_checked,
                "actions_taken": actions_taken,
                "errors_count": errors_count + 1,
                "details": {"error": "Panel JWT expired"},
            })
            if notifier:
                await notifier.send(
                    "⚠️ <b>Panel JWT токен истёк!</b>\n\n"
                    "Проверка кампаний пропущена.\n"
                    "Обновите токен в Settings → Panel API → JWT Token"
                )

        except Exception as e:
            logger.error(f"Check run failed: {e}")
            db.update_check_run(run_id, {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "campaigns_checked": campaigns_checked,
                "actions_taken": actions_taken,
                "errors_count": errors_count + 1,
                "details": {"error": str(e)},
            })
            raise

    async def _process_campaign(
        self,
        db: DatabaseService,
        executor: ActionExecutor,
        notifier: TelegramNotifier | None,
        pc: PanelCampaign,
        account_by_panel_id: dict,
        account_by_name: dict,
        keitaro_conversions: dict[str, int],
        now: datetime,
        rule_kwargs: dict | None = None,
    ) -> str:
        """Process a single campaign. Returns 'skipped', 'checked', or 'action'."""

        # Match to DB account: prefer panel_account_id, fallback to name
        db_account = None
        if pc.panel_account_id:
            db_account = account_by_panel_id.get(pc.panel_account_id)
        if not db_account:
            db_account = account_by_name.get(pc.account_name)
        if not db_account:
            logger.warning(
                f"Campaign {pc.name} ({pc.campaign_id}): "
                f"account '{pc.account_name}' (panel_id={pc.panel_account_id}) "
                f"not found in DB — skipped"
            )
            return "skipped"

        fb_account_id = db_account["id"]

        # Always sync campaign status to DB (even if PAUSED)
        db_campaign = self._sync_campaign(db, pc, fb_account_id)

        # Skip non-active campaigns in FB
        if pc.effective_status != "ACTIVE":
            logger.debug(f"Campaign {pc.name}: FB status {pc.effective_status} — skipped")
            return "skipped"

        # Skip non-managed or stopped campaigns
        if not db_campaign.get("is_managed", True):
            logger.debug(f"Campaign {pc.name}: not managed — skipped")
            return "skipped"
        if db_campaign.get("status") == "stopped":
            logger.debug(f"Campaign {pc.name}: stopped in DB — skipped")
            return "skipped"

        # Leads: prefer Keitaro (sub_id_2 = campaign_id), fallback to Panel FB leads
        keitaro_leads = keitaro_conversions.get(pc.campaign_id, None)
        if keitaro_leads is not None:
            leads = keitaro_leads
        else:
            leads = pc.leads_fb
            if keitaro_conversions:
                logger.debug(
                    f"Campaign {pc.name}: no Keitaro data for campaign_id "
                    f"{pc.campaign_id}, using Panel leads ({leads})"
                )

        state = CampaignState(
            spend=pc.spend,
            leads=leads,
            current_budget=pc.daily_budget,
            last_budget_change_at=_parse_dt(db_campaign.get("last_budget_change_at")),
            link_clicks=pc.link_clicks,
        )

        action = evaluate(state, now, **(rule_kwargs or {}))

        if action.type == ActionType.WAIT:
            return "checked"

        logger.info(
            f"Campaign {pc.name} ({pc.campaign_id}): "
            f"spend=${pc.spend:.2f}, leads={leads} → {action.type.value}: {action.reason}"
        )

        success = await executor.execute(
            action=action,
            campaign_db_id=db_campaign["id"],
            panel_internal_id=pc.internal_id,
            fb_account_id=fb_account_id,
        )

        # Notify on STOP / MANUAL_REVIEW
        if action.type in (ActionType.STOP, ActionType.MANUAL_REVIEW) and notifier:
            try:
                label = "STOP" if action.type == ActionType.STOP else "Manual review"
                await notifier.send(
                    f"{label}: {pc.name}\n"
                    f"Spend: ${pc.spend:.2f}, Leads: {leads}\n"
                    f"Reason: {action.reason}"
                )
            except Exception as e:
                logger.error(f"Telegram notification failed: {e}")

        return "action" if success else "checked"

    @staticmethod
    def _update_account_fb_ids(db: DatabaseService, campaigns: list):
        """Update accounts with real FB ad account IDs extracted from campaign cab data."""
        fb_ids_by_panel_account: dict[int, str] = {}
        for pc in campaigns:
            if pc.fb_ad_account_id and pc.panel_account_id and pc.fb_ad_account_id != "0":
                fb_ids_by_panel_account[pc.panel_account_id] = pc.fb_ad_account_id

        for panel_id, fb_id in fb_ids_by_panel_account.items():
            clean_id = fb_id.replace("act_", "")
            db.upsert_account_by_panel_id(panel_id, {"account_id": clean_id})
            logger.info(f"Updated account panel_id={panel_id} with real FB account ID: {clean_id}")

    @staticmethod
    async def _sync_accounts_from_panel(panel: PanelClient, db: DatabaseService, today: str):
        """Pull accounts from Panel API and upsert into DB."""
        panel_accounts = await panel.get_accounts(
            start_date=today, end_date=today,
        )
        for pa in panel_accounts:
            account_data = {
                "name": pa.name,
                "panel_account_id": pa.internal_id,
                "is_active": True,
            }
            # Store real FB account ID if available from accounts API
            if pa.fb_account_id and pa.fb_account_id != "0":
                account_data["account_id"] = pa.fb_account_id
            else:
                # Only set panel_XXXX fallback if account doesn't already have a real ID
                existing = db.get_account_by_panel_id(pa.internal_id)
                if not existing or (existing.get("account_id", "").startswith("panel_")):
                    account_data["account_id"] = f"panel_{pa.internal_id}"
            db.upsert_account_by_panel_id(pa.internal_id, account_data)

    @staticmethod
    def _sync_campaign(db: DatabaseService, pc: PanelCampaign, fb_account_id: str) -> dict:
        """Sync Panel campaign data to DB, preserving 'stopped' status."""
        existing = db.get_campaign_by_fb_ids(
            str(fb_account_id), str(pc.campaign_id),
        )

        update_data = {
            "panel_campaign_id": pc.internal_id,
            "fb_campaign_name": pc.name,
            "current_budget": pc.daily_budget,
            "total_spend": pc.spend,
            "leads_count": pc.leads_fb,
            "last_fb_sync": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            if existing.get("status") == "stopped" and pc.effective_status == "ACTIVE":
                # Campaign was stopped by system but manually restarted in FB
                logger.info(
                    f"Campaign {pc.name} ({pc.campaign_id}) was stopped but "
                    f"restarted in FB — unlocking to active"
                )
                update_data["status"] = "active"
            elif existing.get("status") != "stopped":
                update_data["status"] = (
                    "active" if pc.effective_status == "ACTIVE" else "paused"
                )
            return db.update_campaign(existing["id"], update_data)

        # New campaign
        update_data.update({
            "fb_account_id": str(fb_account_id),
            "fb_campaign_id": str(pc.campaign_id),
            "status": "active" if pc.effective_status == "ACTIVE" else "paused",
        })
        return db.upsert_campaign(update_data)


def _parse_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None
