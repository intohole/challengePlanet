from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.challenge_service import ChallengeService
from app.services.goal_rule_service import is_cap_mode, is_settled
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import today_str, shift_date


def _day_num(start: str, date_str: str) -> int:
    from datetime import date as _d
    s = _d.fromisoformat(start)
    t = _d.fromisoformat(date_str)
    return (t - s).days + 1


async def _make_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, maker


def _add_challenge(session, **kw) -> Challenge:
    ch = Challenge(**kw)
    session.add(ch)
    return ch


def _add_checkin(session, ch: Challenge, date_str: str, value: float) -> None:
    session.add(CheckIn(
        challenge_id=ch.id, user_id=ch.user_id, day_number=_day_num(ch.start_date, date_str),
        status="completed", timestamp=datetime.fromisoformat(date_str + "T10:00:00"),
        date=date_str, value=value, unit=ch.unit, target_value=1.0,
    ))


@pytest.mark.asyncio
async def test_cap_mode_smoking_scenario() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        start = shift_date(today, -4)
        end = shift_date(start, 13)
        ch = _add_challenge(session,
            user_id="u1", title="戒烟", category="quit", task_type="counter", unit="根",
            direction="decrease", goal_type="soft", goal_rule="ladder",
            ladder_start=10.0, ladder_goal=0.0, ladder_interval=1, ladder_step=2.0,
            duration_days=14, start_date=start, end_date=end, status="active",
            target_value=1.0, ai_plan="[]", share_token="t1", color="#ef4444", icon="🚭")
        await session.commit()
        await session.refresh(ch)
        assert is_cap_mode(ch) is True

        d0 = start
        d1 = shift_date(start, 1)
        d2 = shift_date(start, 2)
        d3 = shift_date(start, 3)
        _add_checkin(session, ch, d1, 3)
        _add_checkin(session, ch, d2, 9)
        _add_checkin(session, ch, d2, 1)
        _add_checkin(session, ch, d3, 2)
        _add_checkin(session, ch, today, 1)
        await session.commit()

        valid = await load_valid_dates(session, ch.id)
        assert d0 in valid, "zero-record past day auto kept"
        assert d1 in valid, "cap-kept day valid"
        assert d3 in valid, "cap-kept day valid"
        assert d2 not in valid, "over-cap day invalid"
        assert today not in valid, "open day not auto-valid"

        stats = await ChallengeService().get_challenge_stats(session, ch)
        assert stats["completed_days"] == 3, "only past cap-kept days counted"
        assert stats["streak"] == 1, "streak breaks after over-cap day"

        today_view = await ChallengeService().get_today_task(session, ch.id, "u1")
        assert today_view is not None
        assert today_view["settled"] is False, "cap-mode today never declared done"
        assert today_view["today_total"] == 1
        assert is_settled(ch, "counter", 3, 10, 1) is False
    await engine.dispose()


@pytest.mark.asyncio
async def test_binary_decrease_still_declares() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session,
            user_id="u1", title="戒烟打卡", category="quit", task_type="binary", unit="次",
            direction="decrease", goal_type="hard", goal_rule="fixed",
            duration_days=7, start_date=shift_date(today, -1), end_date=shift_date(today, 5),
            status="active", target_value=1.0, ai_plan="[]", share_token="t2",
            color="#ef4444", icon="🚭")
        await session.commit()
        await session.refresh(ch)
        assert is_cap_mode(ch) is False
        _add_checkin(session, ch, today, 0)
        await session.commit()
        today_view = await ChallengeService().get_today_task(session, ch.id, "u1")
        assert today_view is not None
        assert today_view["settled"] is True, "binary decrease declaration still settles"
    await engine.dispose()


@pytest.mark.asyncio
async def test_increase_counter_completed_days_is_distinct() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session,
            user_id="u1", title="喝水", category="build", task_type="counter", unit="杯",
            direction="increase", goal_type="hard", goal_rule="fixed",
            duration_days=7, start_date=shift_date(today, -2), end_date=shift_date(today, 4),
            status="active", target_value=8.0, ai_plan="[]", share_token="t3",
            color="#06b6d4", icon="💧")
        await session.commit()
        await session.refresh(ch)
        assert is_cap_mode(ch) is False
        y1 = shift_date(today, -2)
        y2 = shift_date(today, -1)
        _add_checkin(session, ch, y1, 1)
        _add_checkin(session, ch, y1, 2)
        _add_checkin(session, ch, y1, 3)
        _add_checkin(session, ch, y2, 4)
        await session.commit()
        stats = await ChallengeService().get_challenge_stats(session, ch)
        assert stats["completed_days"] == 2, "distinct days, not record rows"
    await engine.dispose()