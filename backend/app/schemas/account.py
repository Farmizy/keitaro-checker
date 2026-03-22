from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.fb_account import ProxyType


class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    account_id: str = Field(..., min_length=1, description="Facebook account ID (act_XXXXX)")
    fbtool_account_id: Optional[int] = None
    access_token: str = ""
    cookie: str = ""
    useragent: str = ""
    proxy_type: ProxyType = ProxyType.SOCKS5
    proxy_host: str = ""
    proxy_port: int = 0
    proxy_login: str = ""
    proxy_password: str = ""


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    account_id: Optional[str] = None
    fbtool_account_id: Optional[int] = None
    access_token: Optional[str] = None
    cookie: Optional[str] = None
    useragent: Optional[str] = None
    proxy_type: Optional[ProxyType] = None
    proxy_host: Optional[str] = None
    proxy_port: Optional[int] = None
    proxy_login: Optional[str] = None
    proxy_password: Optional[str] = None
    is_active: Optional[bool] = None


class AccountResponse(BaseModel):
    id: UUID
    name: str
    account_id: str
    fbtool_account_id: Optional[int] = None
    is_active: bool
    last_check_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
