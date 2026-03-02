from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger

from app.core.auth import get_current_user
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from app.services.database_service import DatabaseService
from app.services.panel_client import PanelClient

router = APIRouter()


def get_db() -> DatabaseService:
    return DatabaseService()


@router.get("/", response_model=list[AccountResponse])
async def list_accounts(
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    accounts = db.get_accounts()
    return accounts


@router.post("/sync")
async def sync_accounts(
    request: Request,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    """Sync accounts from 2KK Panel API into local DB."""
    panel: PanelClient = request.app.state.panel
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
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    data = payload.model_dump()
    account = db.create_account(data)
    return account


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.put("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: UUID,
    payload: AccountUpdate,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
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
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    deleted = db.delete_account(account_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Account not found")
