from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_db_for_user
from app.services.database_service import DatabaseService

router = APIRouter()


@router.get("/")
async def list_rule_sets(
    db: DatabaseService = Depends(get_db_for_user),
):
    return db.get_rule_sets()


@router.get("/default")
async def get_default_rule_set(
    db: DatabaseService = Depends(get_db_for_user),
):
    rule_set = db.get_default_rule_set()
    if not rule_set:
        raise HTTPException(status_code=404, detail="No default rule set found")
    return rule_set


@router.put("/steps/{step_id}")
async def update_rule_step(
    step_id: UUID,
    data: dict,
    db: DatabaseService = Depends(get_db_for_user),
):
    allowed = {
        "spend_threshold", "leads_min", "leads_max",
        "max_cpl", "action", "new_budget",
        "next_spend_limit", "description",
    }
    filtered = {k: v for k, v in data.items() if k in allowed}
    if not filtered:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    result = db.update_rule_step(step_id, filtered)
    if not result:
        raise HTTPException(status_code=404, detail="Rule step not found")
    return result
