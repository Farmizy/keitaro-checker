from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger

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


@router.post("/test/keitaro")
async def test_keitaro(db: DatabaseService = Depends(get_db_for_user)):
    """Test Keitaro connection with current user settings."""
    from app.services.keitaro_client import KeitaroClient

    s = db.get_user_settings()
    if not s or not s.get("keitaro_url") or not s.get("keitaro_login"):
        raise HTTPException(400, "Keitaro не настроен")
    client = KeitaroClient(
        base_url=s["keitaro_url"],
        login=s.get("keitaro_login"),
        password=s.get("keitaro_password"),
    )
    try:
        await client.ensure_authenticated()
        return {"status": "ok", "message": "Подключение к Keitaro успешно"}
    except Exception as e:
        logger.error(f"Keitaro test failed: {e}")
        raise HTTPException(400, f"Ошибка: {e}")
    finally:
        await client.close()


@router.post("/test/panel")
async def test_panel(db: DatabaseService = Depends(get_db_for_user)):
    """Test Panel API connection with current user settings."""
    from app.services.panel_client import PanelClient

    s = db.get_user_settings()
    if not s or not s.get("panel_jwt"):
        raise HTTPException(400, "Panel API не настроен")
    client = PanelClient(
        base_url=s.get("panel_api_url") or None,
        jwt_token=s["panel_jwt"],
    )
    try:
        from datetime import datetime
        import zoneinfo
        today = datetime.now(zoneinfo.ZoneInfo("Europe/Moscow")).strftime("%Y-%m-%d")
        accounts = await client.get_accounts(start_date=today, end_date=today)
        return {"status": "ok", "message": f"Подключение успешно. Аккаунтов: {len(accounts)}"}
    except Exception as e:
        logger.error(f"Panel test failed: {e}")
        raise HTTPException(400, f"Ошибка: {e}")
    finally:
        await client.close()


@router.post("/test/telegram")
async def test_telegram(db: DatabaseService = Depends(get_db_for_user)):
    """Test Telegram bot connection by sending a test message."""
    from app.services.telegram_notifier import TelegramNotifier

    s = db.get_user_settings()
    if not s or not s.get("telegram_bot_token") or not s.get("telegram_chat_id"):
        raise HTTPException(400, "Telegram не настроен")
    notifier = TelegramNotifier(
        bot_token=s["telegram_bot_token"],
        chat_id=s["telegram_chat_id"],
    )
    try:
        await notifier.send("✅ Тестовое сообщение от FB Budget Manager")
        return {"status": "ok", "message": "Сообщение отправлено"}
    except Exception as e:
        logger.error(f"Telegram test failed: {e}")
        raise HTTPException(400, f"Ошибка: {e}")
    finally:
        await notifier.close()
