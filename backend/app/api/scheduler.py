from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.core.auth import get_current_user
from app.services.scheduler_service import SchedulerService

router = APIRouter()


def _get_scheduler(request: Request) -> SchedulerService:
    sched = getattr(request.app.state, "scheduler", None)
    if not sched:
        raise RuntimeError("Scheduler not initialized")
    return sched


@router.get("/status")
async def status(request: Request, _user=Depends(get_current_user)):
    sched = _get_scheduler(request)
    next_run = sched.next_run_time
    return {
        "status": sched.status,
        "interval_minutes": sched.interval_minutes,
        "next_run": next_run.isoformat() if next_run else None,
    }


@router.post("/trigger")
async def trigger(
    request: Request,
    background_tasks: BackgroundTasks,
    _user=Depends(get_current_user),
):
    sched = _get_scheduler(request)
    background_tasks.add_task(sched.trigger_now)
    return {"status": "triggered"}


@router.post("/pause")
async def pause(request: Request, _user=Depends(get_current_user)):
    sched = _get_scheduler(request)
    sched.pause()
    return {"status": "paused"}


@router.post("/resume")
async def resume(request: Request, _user=Depends(get_current_user)):
    sched = _get_scheduler(request)
    sched.resume()
    return {"status": "running"}
