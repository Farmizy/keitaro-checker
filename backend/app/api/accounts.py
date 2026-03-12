from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.core.auth import get_db_for_user, get_user_panel_client
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from app.services.database_service import DatabaseService
from app.services.panel_client import PanelClient

router = APIRouter()


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    db: DatabaseService = Depends(get_db_for_user),
):
    accounts = db.get_accounts()
    return accounts


@router.post("/sync")
async def sync_accounts(
    db: DatabaseService = Depends(get_db_for_user),
    panel: PanelClient = Depends(get_user_panel_client),
):
    """Sync accounts from 2KK Panel API into local DB."""
    from datetime import datetime
    import zoneinfo

    now = datetime.now(zoneinfo.ZoneInfo("Europe/Moscow"))
    today = now.strftime("%Y-%m-%d")

    panel_accounts = await panel.get_accounts(
        start_date=today, end_date=today,
    )

    synced = 0
    for pa in panel_accounts:
        account_id = pa.fb_account_id or f"panel_{pa.internal_id}"
        db.upsert_account_by_panel_id(pa.internal_id, {
            "name": pa.name,
            "account_id": account_id,
            "panel_account_id": pa.internal_id,
            "is_active": True,
        })
        synced += 1

    logger.info(f"Synced {synced} accounts from Panel API")
    return {"synced": synced, "total": len(panel_accounts)}


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreate,
    db: DatabaseService = Depends(get_db_for_user),
):
    data = payload.model_dump()
    account = db.create_account(data)
    return account


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    db: DatabaseService = Depends(get_db_for_user),
):
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    db: DatabaseService = Depends(get_db_for_user),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    account = db.update_account(account_id, data)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: UUID,
    db: DatabaseService = Depends(get_db_for_user),
):
    deleted = db.delete_account(account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
