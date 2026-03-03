"""Executes rule engine decisions via Panel API and logs to DB."""

import zoneinfo
from datetime import datetime

from loguru import logger

from app.services.panel_client import PanelClient
from app.services.database_service import DatabaseService
from app.services.rule_engine import Action, ActionType


class ActionExecutor:

    def __init__(self, panel: PanelClient, db: DatabaseService):
        self.panel = panel
        self.db = db

    async def execute(
        self,
        action: Action,
        campaign_db_id: str,
        panel_internal_id: int,
        fb_account_id: str,
    ) -> bool:
        """Execute an action and log it. Returns True if action was taken."""
        if action.type == ActionType.WAIT:
            return False

        if action.type == ActionType.SET_BUDGET:
            return await self._set_budget(
                action, campaign_db_id, panel_internal_id, fb_account_id,
            )

        if action.type == ActionType.STOP:
            return await self._stop_campaign(
                action, campaign_db_id, panel_internal_id, fb_account_id,
            )

        if action.type == ActionType.MANUAL_REVIEW:
            return await self._manual_review(action, campaign_db_id, fb_account_id)

        return False

    async def _set_budget(
        self, action: Action, campaign_db_id: str,
        panel_internal_id: int, fb_account_id: str,
    ) -> bool:
        success = False
        error_msg = None
        try:
            success = await self.panel.set_budget(panel_internal_id, action.target_budget)
            if success:
                self.db.update_campaign(campaign_db_id, {
                    "current_budget": action.target_budget,
                    "last_budget_change_at": datetime.now(zoneinfo.ZoneInfo("Europe/Moscow")).isoformat(),
                })
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to set budget for campaign {panel_internal_id}: {e}")

        self._log(campaign_db_id, fb_account_id, "budget_increase", action, success, error_msg)
        return success

    async def _stop_campaign(
        self, action: Action, campaign_db_id: str,
        panel_internal_id: int, fb_account_id: str,
    ) -> bool:
        success = False
        error_msg = None
        try:
            success = await self.panel.pause_campaign(panel_internal_id)
            if success:
                self.db.update_campaign(campaign_db_id, {"status": "stopped"})
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to stop campaign {panel_internal_id}: {e}")

        self._log(campaign_db_id, fb_account_id, "campaign_stop", action, success, error_msg)
        return success

    async def _manual_review(
        self, action: Action, campaign_db_id: str, fb_account_id: str,
    ) -> bool:
        self._log(campaign_db_id, fb_account_id, "manual_review_needed", action, True, None)
        return True

    def _log(
        self, campaign_db_id: str, fb_account_id: str,
        action_type: str, action: Action, success: bool, error_msg: str | None,
    ):
        self.db.create_action_log({
            "campaign_id": str(campaign_db_id),
            "fb_account_id": str(fb_account_id),
            "action_type": action_type,
            "details": {
                "reason": action.reason,
                "target_budget": action.target_budget,
            },
            "success": success,
            "error_message": error_msg,
        })
