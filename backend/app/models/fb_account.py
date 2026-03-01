from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ProxyType(str, Enum):
    SOCKS5 = "socks5"
    HTTP = "http"
    HTTPS = "https"


class FBAccount(BaseModel):
    id: UUID
    name: str
    account_id: str  # act_XXXXX
    panel_account_id: Optional[int] = None
    access_token: str  # encrypted
    cookie: str  # encrypted
    useragent: str
    proxy_type: ProxyType
    proxy_host: str
    proxy_port: int
    proxy_login: str
    proxy_password: str  # encrypted
    hide_comments: bool = False
    is_active: bool = True
    last_check_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime
