import time

import pytest
import jwt as pyjwt
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import get_current_user
from app.config import settings


def _make_token(payload: dict, secret: str | None = None, algorithm: str = "HS256") -> str:
    return pyjwt.encode(payload, secret or settings.supabase_jwt_secret, algorithm=algorithm)


class TestAuth:
    def test_valid_token(self):
        token = _make_token({
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) + 3600,
        })
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        result = get_current_user(creds)
        assert result["sub"] == "user-123"

    def test_expired_token(self):
        token = _make_token({
            "sub": "user-123",
            "aud": "authenticated",
            "exp": int(time.time()) - 10,
        })
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(creds)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_invalid_token(self):
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="garbage-token")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(creds)
        assert exc_info.value.status_code == 401

    def test_wrong_secret(self):
        token = _make_token(
            {"sub": "user-123", "aud": "authenticated", "exp": int(time.time()) + 3600},
            secret="wrong-secret-key!!!!!!!!!!!!!!!!!",
        )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(creds)
        assert exc_info.value.status_code == 401
