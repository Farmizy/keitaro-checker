from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.fb_account import ProxyType


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    account_id: str = Field(..., min_length=1, description="Facebook account ID (act_XXXXX)")
    panel_account_id: Optional[int] = None
    access_token: str = Field(..., min_length=1)
    cookie: str = Field(..., min_length=1)
    useragent: str = Field(..., min_length=1)
    proxy_type: ProxyType
    proxy_host: str = Field(..., min_length=1)
    proxy_port: int = Field(..., ge=1, le=65535)
    proxy_login: str = Field(..., min_length=1)
    proxy_password: str = Field(..., min_length=1)


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    account_id: Optional[str] = None
    panel_account_id: Optional[int] = None
    access_token: Optional[str] = None
    cookie: Optional[str] = None
    useragent: Optional[str] = None
    proxy_type: Optional[ProxyType] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = Field(None, ge=1, le=65535)
    proxy_login: Optional[str] = None
    proxy_password: Optional[str] = None
    is_active: Optional[bool] = None


class AccountResponse(BaseModel):
    id: UUID
    name: str
    account_id: str
    panel_account_id: Optional[int] = None
    useragent: str
    proxy_type: ProxyType
    proxy_host: str
    proxy_port: int
    proxy_login: str
    # access_token, cookie, proxy_password — never returned
    hide_comments: bool
    is_active: bool
    last_check_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
