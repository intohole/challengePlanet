from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.adaptive_service import AdaptiveService
from app.services.goal_rule_service import (
    daily_target,
    ladder_cap,
    ladder_goal_day,
)
from app.services.streak_service import shift_date, today_str


async def _make_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, maker


def _ladder_challenge(session, **kw) -> Challenge:
    ch = Challenge(
        user_id="u1", title="戒断挑战", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
        duration_days=66, status="active",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        ladder_adjust=json.dumps([{"day": 6, "shift": 2}]),
        target_value=12.0, ai_plan="[]", share_token="trest", color="#ef4444", icon="🚭",
        start_date=shift_date(today_str(), -34), end_date=shift_date(today_str(), 31),
        **kw,
    )
    session.add(ch)
    return ch


def _day_number(ch: Challenge, date_str: str) -> int:
    from datetime import datetime as _dt

    start = _dt.strptime(str(ch.start_date), "%Y-%m-%d").date()
    target = _dt.strptime(date_str, "%Y-%m-%d").date()
    return (target - start).days + 1


@pytest.mark.asyncio
async def test_anchor_curve_before_unchanged_after_rebased() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.commit()
        today = today_str()
        anchor_day = _day_number(ch, today)
        assert ladder_cap(ch, anchor_day) == 3.0
        pre_days = [anchor_day - 5, anchor_day - 3, anchor_day - 1]
        caps_before = [ladder_cap(ch, d) for d in pre_days]
        ch.ladder_restart = json.dumps({"date": today, "cap": 7})
        assert [ladder_cap(ch, d) for d in pre_days] == caps_before
        assert ladder_cap(ch, anchor_day) == 7.0
        assert ladder_cap(ch, anchor_day + 1) == 7.0
        assert ladder_cap(ch, anchor_day + 2) == 6.0
        assert ladder_cap(ch, anchor_day + 8) == 3.0
        assert ladder_cap(ch, anchor_day + 20) == 3.0


@pytest.mark.asyncio
async def test_goal_day_recalculated_after_anchor() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.commit()
        today = today_str()
        anchor_day = _day_number(ch, today)
        assert ladder_goal_day(ch) is not None
        ch.ladder_restart = json.dumps({"date": today, "cap": 7})
        new_goal_day = ladder_goal_day(ch)
        assert new_goal_day is not None
        assert new_goal_day > anchor_day
        assert ladder_cap(ch, new_goal_day) == 3.0


@pytest.mark.asyncio
async def test_daily_target_reflects_anchor() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.commit()
        today = today_str()
        assert daily_target(ch, _day_number(ch, today)) == 3.0
        ch.ladder_restart = json.dumps({"date": today, "cap": 7})
        assert daily_target(ch, _day_number(ch, today)) == 7.0


async def _seed_gap_records(session, ch: Challenge, gap_days: int = 27) -> None:
    from app.core.datetime_utils import now_china

    await session.flush()
    gap_start = shift_date(today_str(), -gap_days)
    for d, v in [
        (shift_date(gap_start, -2), 2.0),
        (gap_start, 5.0),
        (gap_start, 2.0),
    ]:
        session.add(CheckIn(
            challenge_id=ch.id, user_id="u1", date=d, value=v,
            day_number=1, status="done", target_value=12.0,
            timestamp=now_china(),
        ))
    await session.commit()


@pytest.mark.asyncio
async def test_restart_suggestion_created_on_long_gap() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        svc = AdaptiveService()
        suggestion = await svc.evaluate_restart_on_return(session, ch, gap_days=27)
        await session.commit()
        assert suggestion is not None
        assert suggestion.kind == "restart"
        task = json.loads(suggestion.task_json)
        assert task["restart_cap"] == 7.0
        assert task["current_cap"] == 3.0
        assert task["gap_days"] == 27


@pytest.mark.asyncio
async def test_restart_skipped_short_gap_or_no_headroom() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        assert await AdaptiveService().evaluate_restart_on_return(session, ch, gap_days=3) is None
        ch.ladder_restart = json.dumps({"date": today_str(), "cap": 12})
        await session.commit()
        assert await AdaptiveService().evaluate_restart_on_return(session, ch, gap_days=27) is None


@pytest.mark.asyncio
async def test_restart_idempotent_pending_and_rejected() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        svc = AdaptiveService()
        first = await svc.evaluate_restart_on_return(session, ch, gap_days=27)
        await session.commit()
        assert first is not None
        assert await svc.evaluate_restart_on_return(session, ch, gap_days=27) is None
        await svc.respond(session, int(first.id), "u1", accept=False)
        await session.commit()
        assert await svc.evaluate_restart_on_return(session, ch, gap_days=27) is None


@pytest.mark.asyncio
async def test_respond_accept_applies_anchor() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        svc = AdaptiveService()
        suggestion = await svc.evaluate_restart_on_return(session, ch, gap_days=27)
        await session.commit()
        result = await svc.respond(session, int(suggestion.id), "u1", accept=True)
        await session.commit()
        assert result["applied"] is True
        anchor = json.loads(str(ch.ladder_restart))
        assert anchor["cap"] == 7.0
        assert anchor["date"] == today_str()
        assert suggestion.status == "accepted"
        assert daily_target(ch, _day_number(ch, today_str())) == 7.0


@pytest.mark.asyncio
async def test_respond_reject_keeps_calendar_cap() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        svc = AdaptiveService()
        suggestion = await svc.evaluate_restart_on_return(session, ch, gap_days=27)
        await session.commit()
        result = await svc.respond(session, int(suggestion.id), "u1", accept=False)
        await session.commit()
        assert result["applied"] is False
        assert not str(ch.ladder_restart or "")
        assert suggestion.status == "rejected"
        assert daily_target(ch, _day_number(ch, today_str())) == 3.0


@pytest.mark.asyncio
async def test_get_pending_restart_window() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        svc = AdaptiveService()
        suggestion = await svc.evaluate_restart_on_return(session, ch, gap_days=27)
        await session.commit()
        pending = await svc.get_pending(session, int(ch.id), "u1")
        assert pending is not None and pending.kind == "restart"
        suggestion.target_day = suggestion.target_day - 2
        await session.commit()
        pending = await svc.get_pending(session, int(ch.id), "u1")
        assert pending is not None
        suggestion.target_day = suggestion.target_day - 2
        await session.commit()
        pending = await svc.get_pending(session, int(ch.id), "u1")
        assert pending is None


@pytest.mark.asyncio
async def test_mood_chain_retired() -> None:
    import importlib

    mod = importlib.import_module("app.services.adaptive_service")
    assert not hasattr(mod, "evaluate_after_bad_mood_task")
    import app.services.checkin_service as checkin_mod

    assert "evaluate_after_bad_mood_task" not in Path(checkin_mod.__file__).read_text()


@pytest.mark.asyncio
async def test_return_state_carries_restart_block() -> None:
    from app.services.return_service import active_return_state

    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await _seed_gap_records(session, ch)
        await session.commit()
        state = await active_return_state(session, ch, today_str())
        assert state is not None
        assert int(state["gap_days"]) == 26
        restart = state.get("restart")
        assert isinstance(restart, dict)
        assert restart["restart_cap"] == 7.0
        assert restart["current_cap"] == 3.0
        assert restart["status"] == "pending"
        assert int(restart["suggestion_id"]) > 0
        state = await active_return_state(session, ch, today_str())
        assert state["restart"]["suggestion_id"] == restart["suggestion_id"]
