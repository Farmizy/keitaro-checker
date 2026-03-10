"""APScheduler wrapper for campaign check cycle and auto-launcher."""

import zoneinfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

from app.services.campaign_checker import CampaignChecker


class SchedulerService:
    JOB_ID = "campaign_check"
    ANALYSIS_JOB_ID = "auto_launch_analysis"
    LAUNCH_JOB_ID = "auto_launch_execute"

    def __init__(
        self,
        checker: CampaignChecker,
        interval_minutes: int = 10,
        auto_launcher=None,
    ):
        self.checker = checker
        self.interval_minutes = interval_minutes
        self.auto_launcher = auto_launcher
        self.scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)
        self._paused = False

    def start(self):
        self.scheduler.add_job(
            self.checker.run_check,
            IntervalTrigger(minutes=self.interval_minutes),
            id=self.JOB_ID,
            max_instances=1,
            replace_existing=True,
        )

        if self.auto_launcher:
            self._schedule_auto_launcher()

        self.scheduler.start()
        logger.info(f"Scheduler started: check every {self.interval_minutes} min")

    def _schedule_auto_launcher(
        self,
        analysis_hour: int = 23,
        analysis_minute: int = 0,
        launch_hour: int = 4,
        launch_minute: int = 0,
    ):
        self.scheduler.add_job(
            self.auto_launcher.run_analysis,
            CronTrigger(hour=analysis_hour, minute=analysis_minute),
            id=self.ANALYSIS_JOB_ID,
            max_instances=1,
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.auto_launcher.run_launch,
            CronTrigger(hour=launch_hour, minute=launch_minute),
            id=self.LAUNCH_JOB_ID,
            max_instances=1,
            replace_existing=True,
        )
        logger.info(
            f"Auto-launcher: analysis at {analysis_hour}:{analysis_minute:02d}, "
            f"launch at {launch_hour}:{launch_minute:02d} MSK"
        )

    def update_auto_launcher_schedule(self, settings: dict):
        if not self.auto_launcher:
            return
        for job_id in (self.ANALYSIS_JOB_ID, self.LAUNCH_JOB_ID):
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
        self._schedule_auto_launcher(
            analysis_hour=settings.get("analysis_hour", 23),
            analysis_minute=settings.get("analysis_minute", 0),
            launch_hour=settings.get("launch_hour", 4),
            launch_minute=settings.get("launch_minute", 0),
        )

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

    @property
    def auto_launcher_status(self) -> dict:
        analysis = self.scheduler.get_job(self.ANALYSIS_JOB_ID)
        launch = self.scheduler.get_job(self.LAUNCH_JOB_ID)
        return {
            "analysis_next_run": analysis.next_run_time.isoformat() if analysis and analysis.next_run_time else None,
            "launch_next_run": launch.next_run_time.isoformat() if launch and launch.next_run_time else None,
        }
