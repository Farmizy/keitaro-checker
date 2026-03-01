"""APScheduler wrapper for the campaign check cycle."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from app.services.campaign_checker import CampaignChecker


class SchedulerService:
    JOB_ID = "campaign_check"

    def __init__(self, checker: CampaignChecker, interval_minutes: int = 10):
        self.checker = checker
        self.interval_minutes = interval_minutes
        self.scheduler = AsyncIOScheduler()
        self._paused = False

    def start(self):
        self.scheduler.add_job(
            self.checker.run_check,
            IntervalTrigger(minutes=self.interval_minutes),
            id=self.JOB_ID,
            max_instances=1,
            replace_existing=True,
        )
        self.scheduler.start()
        logger.info(f"Scheduler started: check every {self.interval_minutes} min")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    def pause(self):
        job = self.scheduler.get_job(self.JOB_ID)
        if job:
            job.pause()
            self._paused = True
            logger.info("Scheduler paused")

    def resume(self):
        job = self.scheduler.get_job(self.JOB_ID)
        if job:
            job.resume()
            self._paused = False
            logger.info("Scheduler resumed")

    async def trigger_now(self):
        """Run a check immediately (outside the normal interval)."""
        await self.checker.run_check()

    @property
    def status(self) -> str:
        if not self.scheduler.running:
            return "stopped"
        if self._paused:
            return "paused"
        return "running"

    @property
    def next_run_time(self):
        job = self.scheduler.get_job(self.JOB_ID)
        return job.next_run_time if job else None
