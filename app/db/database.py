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
    "sub_goals",
    "checkins",
    "ai_insights",
    "squads",
    "squad_members",
    "squad_nudges",
    "points_ledger",
    "streak_actions",
    "challenge_meta",
    "adaptive_suggestions",
)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


def _import_models() -> None:
    from app.models import adaptive, challenge, checkin, points, squad, sub_goal  # noqa: F401


_WHITELIST_TABLES = frozenset({"challenges", "checkins", "adaptive_suggestions"})

async def _ensure_column(conn: object, table: str, column: str, ddl: str) -> None:
    if table not in _WHITELIST_TABLES:
        raise ValueError(f"migration: table {table} not in whitelist")
    rows = await conn.execute(text(f"PRAGMA table_info({table})"))
    cols = {row[1] for row in rows.fetchall()}
    if column not in cols:
        logger.info("migration: adding column %s.%s", table, column)
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def _drop_legacy_column_compat(conn: object) -> None:
    rows = await conn.execute(text("PRAGMA table_info(checkins)"))
    cols = {row[1] for row in rows.fetchall()}
    legacy = ("checkin_type", "task_type", "task_data")
    for col in legacy:
        if col in cols:
            logger.info("migration: legacy column checkins.%s kept (sqlite drop limited)", col)


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

        await _ensure_column(conn, "challenges", "target_value", "target_value REAL DEFAULT 1.0")
        await _ensure_column(conn, "challenges", "unit", "unit VARCHAR(16) DEFAULT '次'")
        await _ensure_column(conn, "challenges", "direction", "direction VARCHAR(8) DEFAULT 'increase'")
        await _ensure_column(conn, "challenges", "goal_type", "goal_type VARCHAR(8) DEFAULT 'hard'")
        await _ensure_column(conn, "challenges", "goal_rule", "goal_rule VARCHAR(12) DEFAULT 'fixed'")
        await _ensure_column(conn, "challenges", "goal_mode", "goal_mode VARCHAR(8) DEFAULT 'auto'")
        await _ensure_column(conn, "challenges", "ladder_start", "ladder_start REAL DEFAULT 0.0")
        await _ensure_column(conn, "challenges", "ladder_goal", "ladder_goal REAL DEFAULT 0.0")
        await _ensure_column(conn, "challenges", "ladder_interval", "ladder_interval INTEGER DEFAULT 1")
        await _ensure_column(conn, "challenges", "ladder_step", "ladder_step REAL DEFAULT 1.0")
        await _ensure_column(conn, "challenges", "decompose_mode", "decompose_mode VARCHAR(16) DEFAULT 'none'")
        await _ensure_column(conn, "challenges", "slot_hours", "slot_hours INTEGER DEFAULT 1")
        await _ensure_column(conn, "challenges", "slot_target_value", "slot_target_value REAL DEFAULT 0.0")

        await _ensure_column(conn, "checkins", "sub_goal_id", "sub_goal_id INTEGER")
        await _ensure_column(conn, "checkins", "timestamp", "timestamp DATETIME")
        await _ensure_column(conn, "checkins", "value", "value REAL DEFAULT 0.0")
        await _ensure_column(conn, "checkins", "unit", "unit VARCHAR(16) DEFAULT '次'")
        await _ensure_column(conn, "checkins", "target_value", "target_value REAL DEFAULT 0.0")
        await _ensure_column(conn, "checkins", "goal_type", "goal_type VARCHAR(8) DEFAULT 'hard'")
        await _ensure_column(conn, "checkins", "direction", "direction VARCHAR(8) DEFAULT 'increase'")
        await _ensure_column(conn, "checkins", "context_tag", "context_tag VARCHAR(32) DEFAULT ''")
        await _ensure_column(conn, "checkins", "declaration", "declaration TEXT DEFAULT ''")

        await conn.execute(text(
            "UPDATE checkins SET timestamp = created_at WHERE timestamp IS NULL"
        ))
        await conn.execute(text(
            "UPDATE checkins SET value = 1.0 WHERE value = 0.0 AND completion_pct > 0"
        ))

        await _drop_legacy_column_compat(conn)

        await conn.execute(text(
            "UPDATE adaptive_suggestions SET status='expired' WHERE status='pending' AND id NOT IN ("
            "SELECT MAX(id) FROM adaptive_suggestions WHERE status='pending' GROUP BY challenge_id)"
        ))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_adaptive_pending "
            "ON adaptive_suggestions(challenge_id) WHERE status='pending'"
        ))

        rows = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing = {row[0] for row in rows.fetchall()}
        missing = [t for t in _EXPECTED_TABLES if t not in existing]
        if missing:
            raise RuntimeError(f"migration failed, tables still missing: {missing}")
    logger.info("migrations check passed: %d tables ready", len(_EXPECTED_TABLES))
