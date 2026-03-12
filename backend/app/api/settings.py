from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.auth import get_db_for_user
from app.services.database_service import DatabaseService, USER_SETTINGS_ENCRYPTED_FIELDS

router = APIRouter()

MASKED = "***"

SENSITIVE_FIELDS = {"keitaro_password", "panel_jwt", "telegram_bot_token"}


class UserSettingsUpdate(BaseModel):
    keitaro_url: str | None = None
    keitaro_login: str | None = None
    keitaro_password: str | None = None
    panel_api_url: str | None = None
    panel_jwt: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


def _mask_settings(row: dict) -> dict:
    """Mask sensitive fields and add *_configured flags."""
    result = dict(row)

    for field in SENSITIVE_FIELDS:
        value = result.get(field)
        result[field] = MASKED if value else ""

    result["keitaro_configured"] = bool(
        row.get("keitaro_url")
        and row.get("keitaro_login")
        and row.get("keitaro_password")
    )
    result["panel_configured"] = bool(
        row.get("panel_api_url") and row.get("panel_jwt")
    )
    result["telegram_configured"] = bool(
        row.get("telegram_bot_token") and row.get("telegram_chat_id")
    )

    return result


@router.get("/")
async def get_settings(db: DatabaseService = Depends(get_db_for_user)):
    """Get current user settings with masked sensitive fields."""
    row = db.get_user_settings()
    if not row:
        return {
            "keitaro_url": "",
            "keitaro_login": "",
            "keitaro_password": "",
            "panel_api_url": "",
            "panel_jwt": "",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
            "keitaro_configured": False,
            "panel_configured": False,
            "telegram_configured": False,
        }
    return _mask_settings(row)


@router.put("/")
async def update_settings(
    body: UserSettingsUpdate,
    db: DatabaseService = Depends(get_db_for_user),
):
    """Update current user settings. Fields equal to '***' are skipped."""
    data = {}
    for field, value in body.model_dump(exclude_none=True).items():
        if value == MASKED:
            continue
        data[field] = value

    if not data:
        return {"status": "ok", "message": "Nothing to update"}

    row = db.update_user_settings(data)
    return _mask_settings(row)
