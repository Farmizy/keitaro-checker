from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.core.auth import get_db_for_user, get_user_fbtool_client
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from app.services.database_service import DatabaseService
from app.services.fbtool_client import FbtoolClient

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
    fbtool: FbtoolClient = Depends(get_user_fbtool_client),
):
    """Sync accounts from fbtool.pro into local DB."""
    try:
        fbtool_accounts = await fbtool.get_accounts()

        synced = 0
        for fa in fbtool_accounts:
            account_data = {
                "name": fa.name,
                "fbtool_account_id": fa.fbtool_id,
                "is_active": fa.token_status != "Ошибка",
            }
            if fa.primary_ad_account_id:
                account_data["account_id"] = fa.primary_ad_account_id
            db.upsert_account_by_fbtool_id(fa.fbtool_id, account_data)
            synced += 1

        logger.info(f"Synced {synced} accounts from fbtool.pro")
        return {"synced": synced, "total": len(fbtool_accounts)}
    finally:
        await fbtool.close()


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
