import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.config import settings

security = HTTPBearer()

_jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


def get_db_for_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """FastAPI dependency: verify JWT and return DatabaseService scoped to user."""
    from app.services.database_service import DatabaseService

    user = get_current_user(credentials)
    return DatabaseService.for_user(user_id=user["sub"])


async def get_user_panel_client(
    db: "DatabaseService" = Depends(get_db_for_user),
):
    """FastAPI dependency: create PanelClient from user's settings."""
    from app.services.panel_client import PanelClient

    user_settings = db.get_user_settings()
    if not user_settings or not user_settings.get("panel_jwt"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Panel API not configured. Go to Settings and enter your Panel JWT.",
        )
    return PanelClient(
        base_url=user_settings.get("panel_api_url") or None,
        jwt_token=user_settings["panel_jwt"],
    )


async def get_user_keitaro_client(
    db: "DatabaseService" = Depends(get_db_for_user),
):
    """FastAPI dependency: create KeitaroClient from user's settings."""
    from app.services.keitaro_client import KeitaroClient

    user_settings = db.get_user_settings()
    if not user_settings or not user_settings.get("keitaro_url"):
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail="Keitaro not configured. Go to Settings and enter your Keitaro credentials.",
        )
    return KeitaroClient(
        base_url=user_settings["keitaro_url"],
        login=user_settings.get("keitaro_login") or None,
        password=user_settings.get("keitaro_password") or None,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify Supabase JWT using JWKS public key."""
    token = credentials.credentials
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["ES256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.InvalidTokenError as e:
        logger.error("JWT verification failed: {}", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
