from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_current_user
from app.services.database_service import DatabaseService

router = APIRouter()


def _get_db() -> DatabaseService:
    return DatabaseService()


@router.get("/actions")
async def list_action_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    campaign_id: Optional[UUID] = Query(None),
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_action_logs(limit=limit, offset=offset, campaign_id=campaign_id)


@router.get("/check-runs")
async def list_check_runs(
    limit: int = Query(10, ge=1, le=50),
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_latest_check_runs(limit=limit)
