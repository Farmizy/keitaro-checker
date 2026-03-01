from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CampaignStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


class BudgetLevel(str, Enum):
    CAMPAIGN = "campaign"
    ADSET = "adset"


class Campaign(BaseModel):
    id: UUID
    fb_account_id: UUID
    fb_campaign_id: str
    panel_campaign_id: Optional[int] = None
    fb_campaign_name: str
    fb_adset_id: Optional[str] = None
    budget_level: BudgetLevel = BudgetLevel.CAMPAIGN
    status: CampaignStatus = CampaignStatus.ACTIVE
    current_budget: float = 0
    total_spend: float = 0
    leads_count: int = 0
    cpl: float = 0
    is_managed: bool = True
    last_budget_change_at: Optional[datetime] = None
    last_keitaro_sync: Optional[datetime] = None
    last_fb_sync: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
