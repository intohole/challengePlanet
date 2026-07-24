from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from nexus import close_uc_sdk, init_uc_sdk
from nexus.logging import get_logger

from app.api.adaptive import router as adaptive_router
from app.api.auth import router as auth_router
from app.api.challenge import router as challenge_router
from app.api.checkin import router as checkin_router
from app.api.points import router as points_router
from app.api.portal import router as portal_router
from app.api.scene import router as scene_router
from app.api.share import router as share_router
from app.api.squad import router as squad_router
from app.config import settings
from app.core.middleware import register_middleware
from app.db.database import init_db, run_migrations
from app.infra.ironman_bootstrap import init_ironman, is_ironman_available

logger = get_logger("challengePlanet.main")

_STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await run_migrations()
    if not is_ironman_available():
        try:
            await init_ironman()
        except Exception as e:
            logger.warning("Ironman init failed (Lion may be offline): %s", e)
    logger.info("Ironman available: %s", is_ironman_available())
    if settings.UC_BASE_URL and settings.UC_APP_KEY:
        try:
            init_uc_sdk(
                base_url=settings.UC_BASE_URL,
                app_key=settings.UC_APP_KEY,
                app_secret=settings.UC_APP_SECRET,
                jwt_secret=settings.UC_JWT_SECRET or "",
            )
            logger.info("UC SDK initialized: %s", settings.UC_BASE_URL)
        except Exception as e:
            logger.warning("UC SDK init failed: %s", e)
    yield
    try:
        await close_uc_sdk()
    except Exception:
        pass


app = FastAPI(
    title="ChallengePlanet",
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
register_middleware(app)

API_PREFIX = settings.API_PREFIX
app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(challenge_router, prefix=API_PREFIX + "/challenges")
app.include_router(checkin_router, prefix=API_PREFIX + "/challenges")
app.include_router(adaptive_router, prefix=API_PREFIX + "/challenges")
app.include_router(squad_router, prefix=API_PREFIX)
app.include_router(points_router, prefix=API_PREFIX)
app.include_router(portal_router, prefix=API_PREFIX)
app.include_router(scene_router, prefix=API_PREFIX)
app.include_router(share_router, prefix=API_PREFIX)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "ironman": "available" if is_ironman_available() else "unavailable",
    }


@app.get("/health/detailed")
async def health_detailed() -> dict[str, object]:
    import httpx
    from sqlalchemy import text
    from app.db.database import async_session

    checks: dict[str, object] = {}
    overall = True

    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            checks["database"] = "ok" if result.scalar() == 1 else "error"
    except Exception:
        checks["database"] = "error"
        overall = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.LION_BASE_URL}/health")
            checks["lion"] = "ok" if resp.status_code == 200 else f"status:{resp.status_code}"
            if resp.status_code != 200:
                overall = False
    except Exception:
        checks["lion"] = "error"
        overall = False

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.UC_BASE_URL}/health")
            checks["usercenter"] = "ok" if resp.status_code == 200 else f"status:{resp.status_code}"
            if resp.status_code != 200:
                overall = False
    except Exception:
        checks["usercenter"] = "error"
        overall = False

    checks["ironman"] = "available" if is_ironman_available() else "unavailable"
    if not is_ironman_available():
        overall = False

    return {
        "status": "ok" if overall else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "checks": checks,
    }


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/login")
async def login_page() -> FileResponse:
    login_path = _STATIC_DIR / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return FileResponse(str(_STATIC_DIR / "index.html"))
