from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ActionType(str, Enum):
    BUDGET_INCREASE = "budget_increase"
    CAMPAIGN_STOP = "campaign_stop"
    CAMPAIGN_PAUSE = "campaign_pause"
    MANUAL_REVIEW_NEEDED = "manual_review_needed"


class RuleSet(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    is_default: bool = False


class RuleStep(BaseModel):
    id: UUID
    rule_set_id: UUID
    step_order: int
    spend_threshold: Optional[float] = None
    leads_min: Optional[int] = None
    leads_max: Optional[int] = None
    max_cpl: Optional[float] = None
    action: ActionType
    new_budget: Optional[float] = None
    next_spend_limit: Optional[float] = None
    description: Optional[str] = None
