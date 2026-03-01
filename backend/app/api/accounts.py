from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_user
from app.schemas.account import AccountCreate, AccountUpdate, AccountResponse
from app.services.database_service import DatabaseService

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
