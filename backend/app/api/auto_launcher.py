"""Auto-Launcher API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.core.auth import get_current_user
from app.services.database_service import DatabaseService

router = APIRouter()


def _get_db() -> DatabaseService:
    return DatabaseService()


class SettingsUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    analysis_hour: Optional[int] = None
    analysis_minute: Optional[int] = None
    launch_hour: Optional[int] = None
    launch_minute: Optional[int] = None
    min_roi_threshold: Optional[float] = None
    starting_budget: Optional[float] = None
    new_campaign_max_activity_days: Optional[int] = None
    proven_min_activity_days: Optional[int] = None
    blacklist_zero_leads_days: Optional[int] = None


# --- Settings ---

@router.get("/settings")
async def get_settings(
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_auto_launch_settings() or {}


@router.patch("/settings")
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    result = db.update_auto_launch_settings(data)

    time_fields = {"analysis_hour", "analysis_minute", "launch_hour", "launch_minute"}
    if time_fields & data.keys():
        sched = getattr(request.app.state, "scheduler", None)
        if sched:
            full = db.get_auto_launch_settings()
            sched.update_auto_launcher_schedule(full)

    return result


# --- Queue ---

@router.get("/queue")
async def get_queue(
    launch_date: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_launch_queue(launch_date=launch_date, status=status)


@router.delete("/queue/{item_id}")
async def remove_from_queue(
    item_id: UUID,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.update_launch_queue_item(str(item_id), {
        "status": "removed",
        "removal_reason": "Removed via UI",
    })


# --- Blacklist ---

@router.get("/blacklist")
async def get_blacklist(
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.get_blacklist()


@router.post("/blacklist")
async def add_to_blacklist(
    data: dict,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    return db.add_to_blacklist({
        "campaign_id": data["campaign_id"],
        "fb_campaign_id": data.get("fb_campaign_id", ""),
        "fb_campaign_name": data.get("fb_campaign_name", ""),
        "reason": "manual",
        "blacklisted_by": "user",
    })


@router.delete("/blacklist/{campaign_id}")
async def remove_from_blacklist(
    campaign_id: UUID,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    if not db.remove_from_blacklist(str(campaign_id)):
        raise HTTPException(404, "Not found")
    return {"status": "ok"}


# --- Triggers ---

@router.post("/trigger-analysis")
async def trigger_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    _user=Depends(get_current_user),
):
    al = getattr(request.app.state, "auto_launcher", None)
    if not al:
        raise HTTPException(500, "AutoLauncher not initialized")
    background_tasks.add_task(al.run_analysis)
    return {"status": "triggered"}


@router.post("/trigger-launch")
async def trigger_launch(
    request: Request,
    background_tasks: BackgroundTasks,
    _user=Depends(get_current_user),
):
    al = getattr(request.app.state, "auto_launcher", None)
    if not al:
        raise HTTPException(500, "AutoLauncher not initialized")
    background_tasks.add_task(al.run_launch)
    return {"status": "triggered"}


# --- Status ---

@router.get("/status")
async def get_status(
    request: Request,
    _user=Depends(get_current_user),
    db: DatabaseService = Depends(_get_db),
):
    sched = getattr(request.app.state, "scheduler", None)
    settings = db.get_auto_launch_settings()

    today = datetime.now().strftime("%Y-%m-%d")
    today_queue = db.get_launch_queue(launch_date=today)

    return {
        "is_enabled": settings.get("is_enabled", False) if settings else False,
        "schedule": sched.auto_launcher_status if sched else {},
        "today_queue": {
            "total": len(today_queue),
            "pending": sum(1 for q in today_queue if q["status"] == "pending"),
            "launched": sum(1 for q in today_queue if q["status"] == "launched"),
            "skipped": sum(1 for q in today_queue if q["status"] == "skipped"),
            "failed": sum(1 for q in today_queue if q["status"] == "failed"),
            "removed": sum(1 for q in today_queue if q["status"] == "removed"),
        },
    }
