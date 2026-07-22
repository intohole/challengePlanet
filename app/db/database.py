from __future__ import annotations

from pathlib import Path

from nexus.logging import get_logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = get_logger("challengePlanet.db")


class Base(DeclarativeBase):
    pass


_db_path = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))
_db_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_EXPECTED_TABLES = (
    "challenges",
    "checkins",
    "ai_insights",
    "squads",
    "squad_members",
    "squad_nudges",
    "points_ledger",
    "streak_actions",
    "challenge_meta",
)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def _import_models() -> None:
    from app.models import challenge, checkin, points, squad  # noqa: F401


async def init_db() -> None:
    _import_models()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def run_migrations() -> None:
    _import_models()
    async with engine.begin() as conn:
        rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing = {row[0] for row in rows.fetchall()}
        for table in _EXPECTED_TABLES:
            if table not in existing:
                logger.warning("migration: missing table %s, creating", table)
        await conn.run_sync(Base.metadata.create_all)
        rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing = {row[0] for row in rows.fetchall()}
        missing = [t for t in _EXPECTED_TABLES if t not in existing]
        if missing:
            raise RuntimeError(f"migration failed, tables still missing: {missing}")
    logger.info("migrations check passed: %d tables ready", len(_EXPECTED_TABLES))
