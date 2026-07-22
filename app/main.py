from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.challenge import router as challenge_router
from app.api.checkin import router as checkin_router
from app.api.share import router as share_router
from app.config import settings
from app.db.database import init_db
from app.infra.ironman_bootstrap import init_ironman

_STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await init_ironman()
    except Exception as e:
        print(f"Warning: ironman init failed: {e}")
    yield


app = FastAPI(title="ChallengePlanet", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

API_PREFIX = settings.API_PREFIX
app.include_router(challenge_router, prefix=API_PREFIX + "/challenges")
app.include_router(checkin_router, prefix=API_PREFIX + "/challenges")
app.include_router(share_router, prefix=API_PREFIX + "/challenges")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/login")
async def login_page() -> FileResponse:
    login_path = _STATIC_DIR / "login.html"
    if login_path.exists():
        return FileResponse(str(login_path))
    return FileResponse(str(_STATIC_DIR / "index.html"))
