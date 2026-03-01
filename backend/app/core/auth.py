import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger

from app.config import settings

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """Verify Supabase JWT and return user payload."""
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg", "HS256")
        logger.debug("JWT header: {}", header)

        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[alg],
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
        header_info = {}
        try:
            header_info = jwt.get_unverified_header(token)
        except Exception:
            pass
        logger.error("JWT failed: {} | alg={} | secret_len={}", e, header_info.get("alg"), len(settings.supabase_jwt_secret))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
