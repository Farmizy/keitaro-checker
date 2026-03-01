from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel

from app.models.rule import ActionType


class ActionLog(BaseModel):
    id: UUID
    campaign_id: UUID
    fb_account_id: UUID
    action_type: ActionType
    rule_step_id: Optional[UUID] = None
    details: dict[str, Any] = {}
    success: bool = True
    error_message: Optional[str] = None
    created_at: datetime


class CheckRunStatus(str):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class CheckRun(BaseModel):
    id: UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    campaigns_checked: int = 0
    actions_taken: int = 0
    errors_count: int = 0
    details: dict[str, Any] = {}
