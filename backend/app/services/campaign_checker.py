"""Orchestrator for the 20-minute campaign check cycle.

Multi-tenant: iterates over all users with configured settings,
creates per-user clients, runs checks independently.

Flow per user:
1. For each fbtool account: fetch campaigns + spend from fbtool.pro
2. Fetch conversions from Keitaro
3. Sync campaigns to DB
4. For each active campaign: evaluate rules → execute action → log
"""

import zoneinfo
from datetime import datetime, timezone

from loguru import logger

from app.services.fbtool_client import FbtoolClient, FbtoolCampaign, FbtoolAuthError
from app.services.keitaro_client import KeitaroClient, KeitaroLoginBlocked
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

            # Skip users without fbtool cookies (not configured)
            if not user_settings.get("fbtool_cookies"):
                logger.debug(f"User {user_id}: no fbtool_cookies — skipped")
                continue

            user_db = DatabaseService.admin(user_id=user_id)
            fbtool = FbtoolClient(cookies=user_settings["fbtool_cookies"])
            keitaro = KeitaroClient(
                base_url=user_settings.get("keitaro_url") or None,
                login=user_settings.get("keitaro_login") or None,
                password=user_settings.get("keitaro_password") or None,
            )
            executor = ActionExecutor(fbtool=fbtool, db=user_db)

            notifier = None
            if user_settings.get("telegram_bot_token") and user_settings.get("telegram_chat_id"):
                notifier = TelegramNotifier(
                    bot_token=user_settings["telegram_bot_token"],
                    chat_id=user_settings["telegram_chat_id"],
                )

            # fbtool_account_ids from user settings (JSON list)
            fbtool_account_ids = user_settings.get("fbtool_account_ids") or []
            if not fbtool_account_ids:
                logger.warning(f"User {user_id}: no fbtool_account_ids configured — skipped")
                continue

            try:
                await self._run_check_for_user(
                    fbtool, keitaro, user_db, executor, notifier, fbtool_account_ids,
                )
            except Exception as e:
                logger.error(f"Check failed for user {user_id}: {e}")
            finally:
                await fbtool.close()
                await keitaro.close()
                if notifier:
                    await notifier.close()

    async def _run_check_for_user(
        self,
        fbtool: FbtoolClient,
        keitaro: KeitaroClient,
        db: DatabaseService,
        executor: ActionExecutor,
        notifier: TelegramNotifier | None,
        fbtool_account_ids: list[int],
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

            # 1. Sync accounts from fbtool
            logger.info("Syncing accounts from fbtool...")
            await self._sync_accounts_from_fbtool(fbtool, db)
            db_accounts = db.get_active_accounts()
            logger.info(f"Got {len(db_accounts)} accounts from DB")

            # 2. Fetch campaigns from fbtool for each account
            logger.info("Fetching campaigns from fbtool...")
            all_fbtool_campaigns: list[FbtoolCampaign] = []
            for account_id in fbtool_account_ids:
                try:
                    campaigns = await fbtool.get_campaigns(account_id, today)
                    all_fbtool_campaigns.extend(campaigns)
                except Exception as e:
                    errors_count += 1
                    logger.error(f"Failed to fetch campaigns for fbtool account {account_id}: {e}")

            logger.info(f"Got {len(all_fbtool_campaigns)} campaigns from fbtool")

            # 3. Fetch conversions from Keitaro (grouped by campaign_id via sub_id_2)
            logger.info("Fetching conversions from Keitaro...")
            keitaro_conversions: dict[str, int] = {}
            keitaro_available = True
            try:
                await keitaro.ensure_authenticated()
                keitaro_conversions = await keitaro.get_all_conversions_by_campaign()
                logger.info(f"Got conversions for {len(keitaro_conversions)} campaign IDs from Keitaro")
            except KeitaroLoginBlocked as e:
                keitaro_available = False
                logger.warning(f"Keitaro login blocked (rate limit), skipping: {e}")
            except Exception as e:
                keitaro_available = False
                logger.error(f"Keitaro fetch failed, using fbtool leads as fallback: {e}")
                if notifier:
                    try:
                        await notifier.send(
                            "⚠️ <b>Keitaro недоступен</b>\n\n"
                            f"Ошибка: {e}\n"
                            "Проверка использует лиды из fbtool как fallback."
                        )
                    except Exception:
                        pass

            # 4. Build account mappings by fbtool_account_id
            account_by_fbtool_id = {
                acc["fbtool_account_id"]: acc
                for acc in db_accounts
                if acc.get("fbtool_account_id")
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
            for fc in all_fbtool_campaigns:
                try:
                    result = await self._process_campaign(
                        db, executor, notifier,
                        fc, account_by_fbtool_id, account_by_name,
                        keitaro_conversions, now, rule_kwargs,
                    )
                    if result == "checked":
                        campaigns_checked += 1
                    elif result == "action":
                        campaigns_checked += 1
                        actions_taken += 1
                except Exception as e:
                    errors_count += 1
                    logger.error(f"Error processing campaign {fc.fb_campaign_id}: {e}")

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

        except FbtoolAuthError as e:
            logger.error(f"Fbtool session expired, skipping check cycle: {e}")
            db.update_check_run(run_id, {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "campaigns_checked": campaigns_checked,
                "actions_taken": actions_taken,
                "errors_count": errors_count + 1,
                "details": {"error": "Fbtool session expired"},
            })
            if notifier:
                await notifier.send(
                    "⚠️ <b>Fbtool сессия истекла!</b>\n\n"
                    "Проверка кампаний пропущена.\n"
                    "Перелогиньтесь на fbtool.pro и обновите cookies в Settings."
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
        fc: FbtoolCampaign,
        account_by_fbtool_id: dict,
        account_by_name: dict,
        keitaro_conversions: dict[str, int],
        now: datetime,
        rule_kwargs: dict | None = None,
    ) -> str:
        """Process a single campaign. Returns 'skipped', 'checked', or 'action'."""

        # Match to DB account: prefer fbtool_account_id, fallback to name
        db_account = None
        if fc.fbtool_account_id:
            db_account = account_by_fbtool_id.get(fc.fbtool_account_id)
        if not db_account:
            db_account = account_by_name.get(fc.account_name)
        if not db_account:
            logger.warning(
                f"Campaign {fc.name} ({fc.fb_campaign_id}): "
                f"account '{fc.account_name}' (fbtool_id={fc.fbtool_account_id}) "
                f"not found in DB — skipped"
            )
            return "skipped"

        fb_account_id = db_account["id"]

        # Always sync campaign status to DB (even if PAUSED)
        db_campaign = self._sync_campaign(db, fc, fb_account_id)

        # Skip non-active campaigns in FB
        if fc.effective_status != "ACTIVE":
            logger.debug(f"Campaign {fc.name}: FB status {fc.effective_status} — skipped")
            return "skipped"

        # Skip non-managed or stopped campaigns
        if not db_campaign.get("is_managed", True):
            logger.debug(f"Campaign {fc.name}: not managed — skipped")
            return "skipped"
        if db_campaign.get("status") == "stopped":
            logger.debug(f"Campaign {fc.name}: stopped in DB — skipped")
            return "skipped"

        # Leads: prefer Keitaro (sub_id_2 = campaign_id), fallback to fbtool leads
        keitaro_leads = keitaro_conversions.get(fc.fb_campaign_id, None)
        if keitaro_leads is not None:
            leads = keitaro_leads
        else:
            leads = fc.leads
            if keitaro_conversions:
                logger.debug(
                    f"Campaign {fc.name}: no Keitaro data for campaign_id "
                    f"{fc.fb_campaign_id}, using fbtool leads ({leads})"
                )

        state = CampaignState(
            spend=fc.spend,
            leads=leads,
            current_budget=fc.daily_budget,
            last_budget_change_at=_parse_dt(db_campaign.get("last_budget_change_at")),
            link_clicks=fc.link_clicks,
        )

        action = evaluate(state, now, **(rule_kwargs or {}))

        if action.type == ActionType.WAIT:
            return "checked"

        logger.info(
            f"Campaign {fc.name} ({fc.fb_campaign_id}): "
            f"spend=${fc.spend:.2f}, leads={leads} → {action.type.value}: {action.reason}"
        )

        success = await executor.execute(
            action=action,
            campaign_db_id=db_campaign["id"],
            fb_campaign_id=fc.fb_campaign_id,
            fbtool_account_id=fc.fbtool_account_id,
            fb_account_id=fb_account_id,
        )

        # Notify on STOP / MANUAL_REVIEW
        if action.type in (ActionType.STOP, ActionType.MANUAL_REVIEW) and notifier:
            try:
                label = "STOP" if action.type == ActionType.STOP else "Manual review"
                await notifier.send(
                    f"{label}: {fc.name}\n"
                    f"Spend: ${fc.spend:.2f}, Leads: {leads}\n"
                    f"Reason: {action.reason}"
                )
            except Exception as e:
                logger.error(f"Telegram notification failed: {e}")

        return "action" if success else "checked"

    @staticmethod
    async def _sync_accounts_from_fbtool(fbtool: FbtoolClient, db: DatabaseService):
        """Pull accounts from fbtool.pro and upsert into DB."""
        fbtool_accounts = await fbtool.get_accounts()
        for fa in fbtool_accounts:
            account_data = {
                "name": fa.name,
                "fbtool_account_id": fa.fbtool_id,
                "is_active": fa.token_status != "Ошибка",
            }
            # Store real FB ad account ID if available
            if fa.primary_ad_account_id:
                account_data["account_id"] = fa.primary_ad_account_id
            db.upsert_account_by_fbtool_id(fa.fbtool_id, account_data)

    @staticmethod
    def _sync_campaign(db: DatabaseService, fc: FbtoolCampaign, fb_account_id: str) -> dict:
        """Sync fbtool campaign data to DB, preserving 'stopped' status."""
        existing = db.get_campaign_by_fb_ids(
            str(fb_account_id), str(fc.fb_campaign_id),
        )

        update_data = {
            "fb_campaign_name": fc.name,
            "current_budget": fc.daily_budget,
            "total_spend": fc.spend,
            "leads_count": fc.leads,
            "last_fb_sync": datetime.now(timezone.utc).isoformat(),
        }

        if existing:
            if existing.get("status") == "stopped" and fc.effective_status == "ACTIVE":
                # Only unlock if stopped more than 60 min ago (fbtool stop takes time to propagate)
                stopped_at = _parse_dt(existing.get("stopped_at"))
                now = datetime.now(timezone.utc)
                if stopped_at and (now - stopped_at).total_seconds() < 3600:
                    logger.debug(
                        f"Campaign {fc.name}: stopped {int((now - stopped_at).total_seconds() // 60)}m ago, "
                        f"keeping stopped (fbtool still shows ACTIVE)"
                    )
                else:
                    # Campaign was stopped by system but manually restarted in FB
                    logger.info(
                        f"Campaign {fc.name} ({fc.fb_campaign_id}) was stopped but "
                        f"restarted in FB — unlocking to active"
                    )
                    update_data["status"] = "active"
            elif existing.get("status") != "stopped":
                update_data["status"] = (
                    "active" if fc.effective_status == "ACTIVE" else "paused"
                )
            return db.update_campaign(existing["id"], update_data)

        # New campaign
        update_data.update({
            "fb_account_id": str(fb_account_id),
            "fb_campaign_id": str(fc.fb_campaign_id),
            "status": "active" if fc.effective_status == "ACTIVE" else "paused",
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
