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

    # Build alerts from recent check runs and user settings
    alerts = _build_alerts(db, recent_runs)

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
        "alerts": alerts,
    }


def _build_alerts(db: DatabaseService, recent_runs: list) -> list[dict]:
    """Build alert list from check runs and user settings."""
    alerts: list[dict] = []

    # Check user settings configuration
    settings = db.get_user_settings()
    if not settings or not settings.get("panel_jwt"):
        alerts.append({
            "type": "warning",
            "key": "panel_not_configured",
            "message": "Panel API не настроен. Настройте JWT токен в Settings.",
        })
    if not settings or not settings.get("keitaro_url") or not settings.get("keitaro_login"):
        alerts.append({
            "type": "info",
            "key": "keitaro_not_configured",
            "message": "Keitaro не настроен. Лиды будут браться из Panel API.",
        })

    if not recent_runs:
        return alerts

    last_run = recent_runs[0]
    details = last_run.get("details") or {}

    # JWT expired
    if last_run.get("status") == "failed" and details.get("error") == "Panel JWT expired":
        alerts.append({
            "type": "error",
            "key": "jwt_expired",
            "message": "Panel JWT токен истёк! Обновите в Settings → Panel API → JWT Token.",
        })

    # Keitaro unavailable
    if details.get("keitaro_available") is False:
        alerts.append({
            "type": "warning",
            "key": "keitaro_unavailable",
            "message": "Keitaro недоступен. Лиды берутся из Panel API как fallback.",
        })

    # Last run had errors
    if last_run.get("errors_count", 0) > 0 and last_run.get("status") != "failed":
        alerts.append({
            "type": "warning",
            "key": "check_errors",
            "message": f"Последняя проверка: {last_run['errors_count']} ошибок.",
        })

    return alerts
