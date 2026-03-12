from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import get_db_for_user
from app.services.database_service import DatabaseService

router = APIRouter()


@router.get("/actions")
async def list_action_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    campaign_id: Optional[UUID] = Query(None),
    db: DatabaseService = Depends(get_db_for_user),
):
    return db.get_action_logs(limit=limit, offset=offset, campaign_id=campaign_id)


@router.get("/check-runs")
async def list_check_runs(
    limit: int = Query(10, ge=1, le=50),
    db: DatabaseService = Depends(get_db_for_user),
):
    return db.get_latest_check_runs(limit=limit)
