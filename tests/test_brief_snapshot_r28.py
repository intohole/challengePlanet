from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.adaptive import AdaptiveSuggestion
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.repositories.adaptive_repository import AdaptiveRepository
from app.services.adaptive_service import RESTART_WINDOW_DAYS, AdaptiveService
from app.services.brief_service import build_brief_snapshot
from app.services.goal_rule_service import daily_target
from app.services.streak_service import day_number_of, shift_date, today_str


async def _make_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, maker


def _ladder_challenge(session, **kw) -> Challenge:
    fields: dict[str, object] = dict(
        user_id="u1", title="戒断挑战", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
        duration_days=66, status="active",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        target_value=12.0, ai_plan="[]", share_token="trest", color="#ef4444", icon="🚭",
        start_date=shift_date(today_str(), -34), end_date=shift_date(today_str(), 31),
    )
    fields.update(kw)
    ch = Challenge(**fields)
    session.add(ch)
    return ch


def _seed_checkin(session, ch: Challenge, days_after_start: int) -> None:
    from datetime import datetime as _dt, timezone

    session.add(CheckIn(
        challenge_id=int(ch.id), user_id=str(ch.user_id), day_number=days_after_start + 1,
        status="completed", timestamp=_dt.now(timezone.utc).replace(tzinfo=None),
        date=shift_date(str(ch.start_date), days_after_start),
        value=5.0, unit=str(ch.unit),
    ))


def _seed_restart(session, ch: Challenge, days_ago: int = 0) -> AdaptiveSuggestion:
    day_now = day_number_of(str(ch.start_date), today_str())
    return AdaptiveSuggestion(
        challenge_id=int(ch.id),
        user_id=str(ch.user_id),
        kind="restart",
        reason="r28 seed",
        task_json=json.dumps({
            "restart_cap": 7.0, "current_cap": daily_target(ch, day_now),
            "gap_days": 30, "unit": str(ch.unit), "title": ch.title,
        }, ensure_ascii=False),
        target_day=day_now - days_ago,
        status="pending",
    )


@pytest.mark.asyncio
async def test_snapshot_shape_and_restart_ctx() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.flush()
        _seed_checkin(session, ch, 3)
        session.add(_seed_restart(session, ch))
        await session.commit()
        snap = await build_brief_snapshot(session, "u1")
        assert snap["status"] == "ok"
        assert snap["has_active"] is True
        assert len(snap["challenges"]) == 1
        item = snap["challenges"][0]
        day_now = day_number_of(str(ch.start_date), today_str())
        assert item["id"] == int(ch.id)
        assert item["title"] == "戒断挑战"
        assert item["icon"] == "🚭"
        assert item["unit"] == "根"
        assert item["today_checked"] is False
        assert item["today_cap"] == daily_target(ch, day_now)
        assert item["today_cap"] != 12.0
        pr = item["return_ctx"]["restart"]
        assert pr is not None
        assert pr["restart_cap"] == 7.0
        assert pr["current_cap"] == item["today_cap"]
        assert pr["remaining_days"] == RESTART_WINDOW_DAYS
        assert item["return_ctx"]["gap_days"] >= 7


@pytest.mark.asyncio
async def test_snapshot_readonly_sentinel() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.flush()
        _seed_checkin(session, ch, 3)
        await session.commit()

        async def _boom(*a, **kw):
            raise AssertionError("brief snapshot 触发了写链")

        repo = AdaptiveRepository()
        repo_create = repo.create
        repo_update = repo.update_status
        repo.create = _boom
        repo.update_status = _boom
        try:
            snap = await build_brief_snapshot(session, "u1")
        finally:
            repo.create = repo_create
            repo.update_status = repo_update
        rows = (await session.execute(select(AdaptiveSuggestion))).scalars().all()
        assert rows == []
        assert snap["challenges"][0]["return_ctx"]["restart"] is None


@pytest.mark.asyncio
async def test_snapshot_pending_restart_sorts_first() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        plain = Challenge(
            user_id="u1", title="读书挑战", category="learn", task_type="counter", unit="页",
            direction="increase", goal_type="soft", goal_rule="fixed", goal_mode="total",
            duration_days=30, status="active", target_value=10.0, ai_plan="[]",
            share_token="t2", color="#22c55e", icon="📖",
            start_date=shift_date(today_str(), -3), end_date=shift_date(today_str(), 26),
        )
        session.add(plain)
        ch = _ladder_challenge(session)
        await session.flush()
        _seed_checkin(session, ch, 3)
        session.add(_seed_restart(session, ch))
        await session.commit()
        snap = await build_brief_snapshot(session, "u1")
        assert snap["challenges"][0]["id"] == int(ch.id)
        assert snap["challenges"][0]["return_ctx"]["restart"] is not None
        assert snap["challenges"][1]["title"] == "读书挑战"
        assert snap["challenges"][1]["return_ctx"]["restart"] is None


@pytest.mark.asyncio
async def test_snapshot_expired_pending_not_surfaced() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.flush()
        _seed_checkin(session, ch, 3)
        session.add(_seed_restart(session, ch, days_ago=RESTART_WINDOW_DAYS + 1))
        await session.commit()
        snap = await build_brief_snapshot(session, "u1")
        assert snap["challenges"][0]["return_ctx"]["restart"] is None


@pytest.mark.asyncio
async def test_snapshot_empty_user_inactive_only() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        _ladder_challenge(session, status="resting", is_shared=True)
        await session.commit()
        snap = await build_brief_snapshot(session, "u1")
        assert snap["status"] == "ok"
        assert snap["has_active"] is False
        assert snap["challenges"] == []


@pytest.mark.asyncio
async def test_get_pending_keeps_expiry_write_behavior() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.flush()
        session.add(_seed_restart(session, ch, days_ago=RESTART_WINDOW_DAYS + 1))
        await session.commit()
        svc = AdaptiveService()
        got = await svc.get_pending(session, int(ch.id), "u1")
        assert got is None
        row = (await session.execute(
            select(AdaptiveSuggestion).where(AdaptiveSuggestion.status == "expired")
        )).scalar_one()
        assert row.kind == "restart"
