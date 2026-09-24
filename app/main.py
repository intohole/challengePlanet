from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from nexus.middleware import LoadingSplashMiddleware, NoCacheMiddleware
from nexus import close_uc_sdk, create_auth_router, get_uc_sdk, init_uc_sdk_from_lion, is_ironman_available, startup_ironman, register_health_detail
from nexus.chat.engine import ChatEngine
from nexus.chat.router import chat_router
from nexus.logging import get_logger, setup_logging
from nexus.notify import async_init_notify_client, register_notify_proxy
from nexus.scheduler import get_scheduler

from app.api.adaptive import router as adaptive_router
from app.api.challenge import router as challenge_router
from app.api.checkin import router as checkin_router
from app.api.diet import router as diet_router
from app.api.points import router as points_router
from app.api.portal import router as portal_router
from app.api.report import router as report_router
from app.api.squad import router as squad_router
from app.config import settings
from app.core.middleware import register_middleware
from app.db.database import init_db, run_migrations, engine as db_engine, async_session
from app.services.reminder_service import send_checkin_reminders
from app.services.forecast_alert_service import send_forecast_alerts
from app.services.challenge_service import ChallengeService
from app.services.challenge_chat_handler import challenge_chat_handler

setup_logging()
logger = get_logger("challengePlanet.main")

_STATIC_DIR = Path(__file__).parent.parent / "static"


async def close_finished_challenges() -> None:
    try:
        async with async_session() as session:
            closed = await ChallengeService().close_finished(session)
            if closed:
                logger.info("已结束挑战自动归档 %d 个", closed)
    except Exception as e:
        logger.error("close finished challenges failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await run_migrations()
    if not is_ironman_available():
        result = await startup_ironman("ChallengePlanet")
        if result.get("degraded"):
            logger.warning("Ironman degraded: %s", result.get("error", "unknown"))
    logger.info("Ironman available: %s", is_ironman_available())
    await async_init_notify_client()
    try:
        await init_uc_sdk_from_lion()
        logger.info("UC SDK initialized from Lion")
    except Exception as e:
        logger.warning("UC SDK init failed: %s", e)
    scheduler = get_scheduler()
    scheduler.add_cron_job(
        send_checkin_reminders,
        job_id="cp-checkin-reminder",
        hour=20,
        minute=0,
    )
    scheduler.add_cron_job(
        send_forecast_alerts,
        job_id="cp-forecast-alert",
        hour=18,
        minute=30,
    )
    scheduler.add_cron_job(
        close_finished_challenges,
        job_id="cp-close-finished",
        hour=0,
        minute=10,
    )
    scheduler.start()
    logger.info("Scheduler started: check-in reminders at 20:00 daily")
    yield
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    try:
        await close_uc_sdk()
    except Exception:
        pass


app = FastAPI(
    title="星轨挑战",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
register_middleware(app)
app.add_middleware(LoadingSplashMiddleware, app_name="星轨挑战")
app.add_middleware(NoCacheMiddleware, path_prefix="/static")

API_PREFIX = settings.API_PREFIX
app.include_router(create_auth_router(prefix="/api/v1/auth", uc_sdk_provider=get_uc_sdk, tags=["认证"], endpoints={"config", "login", "register"}))
app.include_router(challenge_router, prefix=API_PREFIX + "/challenges")
app.include_router(checkin_router, prefix=API_PREFIX + "/challenges")
app.include_router(diet_router, prefix=API_PREFIX + "/challenges")
app.include_router(report_router, prefix=API_PREFIX + "/challenges")
app.include_router(adaptive_router, prefix=API_PREFIX + "/challenges")
app.include_router(squad_router, prefix=API_PREFIX)
app.include_router(points_router, prefix=API_PREFIX)
app.include_router(portal_router, prefix=API_PREFIX)
app.include_router(chat_router(ChatEngine(db_engine).register("challengePlanet", challenge_chat_handler), "challengePlanet"))

register_notify_proxy(app)

app.include_router(create_auth_router(prefix="/api/auth", uc_sdk_provider=get_uc_sdk, tags=["认证"], password_ops=True, endpoints={"config"}))


@app.get("/health")
async def health() -> dict[str, str]:
    scheduler = get_scheduler()
    jobs = scheduler.list_jobs()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ironman": "available" if is_ironman_available() else "unavailable",
        "scheduler": f"running ({len(jobs)} jobs)" if scheduler.running else "stopped",
    }


async def _health_db_check() -> str:
    from sqlalchemy import text
    from app.db.database import async_session

    async with async_session() as session:
        result = await session.execute(text("SELECT 1"))
        return "ok" if result.scalar() == 1 else "error"


async def _health_lion_check() -> str:
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{settings.LION_BASE_URL}/health")
        return "ok" if resp.status_code == 200 else f"status:{resp.status_code}"


async def _health_uc_check() -> str:
    import httpx
    try:
        sdk = get_uc_sdk()
    except Exception:
        return "unavailable"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{sdk.base_url}/health")
        return "ok" if resp.status_code == 200 else f"status:{resp.status_code}"


async def _health_ironman_check() -> str:
    return "ok" if is_ironman_available() else "unavailable"


register_health_detail(
    app,
    app_name=settings.APP_NAME,
    app_version=settings.APP_VERSION,
    checks={
        "database": _health_db_check,
        "lion": _health_lion_check,
        "usercenter": _health_uc_check,
        "ironman": _health_ironman_check,
    },
)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/login")
async def login_page() -> FileResponse:
    login_path = _STATIC_DIR / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return FileResponse(str(_STATIC_DIR / "index.html"))
