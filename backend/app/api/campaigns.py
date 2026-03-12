from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_db_for_user
from app.services.database_service import DatabaseService

router = APIRouter()


@router.get("/")
async def list_campaigns(
    account_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    db: DatabaseService = Depends(get_db_for_user),
):
    return db.get_campaigns(account_id=account_id, status=status)


@router.get("/{campaign_id}")
async def get_campaign(
    campaign_id: UUID,
    db: DatabaseService = Depends(get_db_for_user),
):
    campaign = db.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign


@router.patch("/{campaign_id}")
async def update_campaign(
    campaign_id: UUID,
    data: dict,
    db: DatabaseService = Depends(get_db_for_user),
):
    allowed = {"is_managed", "status", "notes"}
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    result = db.update_campaign(campaign_id, filtered)
    if not result:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return result
