from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api import accounts, campaigns, rules, logs, dashboard, scheduler, generator
from app.api import auto_launcher as auto_launcher_api
from app.api import settings as settings_api
from app.config import settings
from app.services.database_service import DatabaseService
from app.services.campaign_checker import CampaignChecker
from app.services.scheduler_service import SchedulerService
from app.services.auto_launcher import AutoLauncher


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FB Budget Manager")

    admin_db = DatabaseService.admin()

    checker = CampaignChecker(db=admin_db)
    auto_launcher = AutoLauncher(db=admin_db)

    sched = SchedulerService(
        checker=checker,
        interval_minutes=settings.check_interval_minutes,
        auto_launcher=auto_launcher,
    )

    app.state.scheduler = sched
    app.state.auto_launcher = auto_launcher
    sched.start()

    yield

    sched.stop()
    logger.info("Shutting down FB Budget Manager")


app = FastAPI(
    title="FB Budget Manager",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(campaigns.router, prefix="/api/v1/campaigns", tags=["campaigns"])
app.include_router(rules.router, prefix="/api/v1/rules", tags=["rules"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])
app.include_router(scheduler.router, prefix="/api/v1/scheduler", tags=["scheduler"])
app.include_router(generator.router, prefix="/api/v1/generator", tags=["generator"])
app.include_router(settings_api.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(auto_launcher_api.router, prefix="/api/v1/auto-launcher", tags=["auto-launcher"])


@app.get("/health")
async def health():
    return {"status": "ok"}
