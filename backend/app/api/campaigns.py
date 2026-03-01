from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.services.database_service import DatabaseService

router = APIRouter()


def _get_db() -> DatabaseService:
    return DatabaseService()


@router.get("/")
async def list_campaigns(
    account_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_campaigns(account_id=account_id, status=status)


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    campaign = db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    data: dict,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    allowed = {"is_managed", "status", "notes"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    result = db.update_campaign(campaign_id, filtered)
    if not result:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return result
