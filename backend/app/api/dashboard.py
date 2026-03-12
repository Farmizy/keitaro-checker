from fastapi import APIRouter, Depends

from app.core.auth import get_db_for_user
from app.services.database_service import DatabaseService

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: DatabaseService = Depends(get_db_for_user),
):
    campaigns = db.get_campaigns()
    accounts = db.get_accounts()
    recent_logs = db.get_action_logs(limit=10)
    recent_runs = db.get_latest_check_runs(limit=5)

    total_spend = sum(c.get("total_spend", 0) or 0 for c in campaigns)
    total_leads = sum(c.get("leads_count", 0) or 0 for c in campaigns)
    active = sum(1 for c in campaigns if c.get("status") == "active")
    paused = sum(1 for c in campaigns if c.get("status") == "paused")
    stopped = sum(1 for c in campaigns if c.get("status") == "stopped")

    return {
        "total_spend": total_spend,
        "total_leads": total_leads,
        "avg_cpl": total_spend / total_leads if total_leads > 0 else 0,
        "campaigns_active": active,
        "campaigns_paused": paused,
        "campaigns_stopped": stopped,
        "campaigns_total": len(campaigns),
        "accounts_total": len(accounts),
        "accounts_active": sum(1 for a in accounts if a.get("is_active")),
        "recent_actions": recent_logs,
        "recent_runs": recent_runs,
    }
