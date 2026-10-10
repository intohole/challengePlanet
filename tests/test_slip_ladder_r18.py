from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.goal_rule_service import (
    ladder_cap,
    ladder_goal_day,
    parse_ladder_adjustments,
    shifted_day,
)
from app.services.slip_service import assess_slip
from app.services.streak_service import shift_date, today_str


def _day_num(start: str, date_str: str) -> int:
    from datetime import date as _d
    return (_d.fromisoformat(date_str) - _d.fromisoformat(start)).days + 1


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


def _rows(ch: Challenge, values: dict[str, float]) -> list[dict]:
    return [
        {"date": d, "value": v, "checkin_count": 1}
        for d, v in sorted(values.items())
    ]


def test_shifted_day_composes_segments_desc() -> None:
    adjs = [{"day": 3, "shift": 2}, {"day": 10, "shift": 1}]
    assert shifted_day(2, adjs) == 2
    assert shifted_day(3, adjs) == 1
    assert shifted_day(9, adjs) == 7
    assert shifted_day(10, adjs) == 7
    assert shifted_day(11, adjs) == 8
    assert shifted_day(1, adjs) == 1


def test_parse_adjustments_filters_invalid() -> None:
    raw = '[{"day":1,"shift":3},{"day":4,"shift":0},{"day":5,"shift":99},{"day":6,"shift":2},{"bad":1}]'
    adjs = parse_ladder_adjustments(raw)
    assert adjs == [{"day": 6, "shift": 2}]
    assert parse_ladder_adjustments("") == []
    assert parse_ladder_adjustments(None) == []


def test_ladder_cap_history_immutable_after_adjust() -> None:
    today = today_str()
    start = shift_date(today, -2)
    ch = Challenge(
        user_id="u1", title="t", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0, ai_plan="[]",
    )
    plain = [ladder_cap(ch, d) for d in range(1, 12)]
    ch.ladder_adjust = '[{"day":3,"shift":2}]'
    adjusted = [ladder_cap(ch, d) for d in range(1, 12)]
    assert adjusted[0] == plain[0]
    assert adjusted[1] == plain[1]
    assert adjusted[2] == plain[0]
    assert adjusted[3] == plain[1]
    assert adjusted[4] == plain[2]
    assert adjusted[10] == plain[8]
    assert min(adjusted) >= 3.0


def test_goal_day_walks_with_shift() -> None:
    today = today_str()
    start = shift_date(today, -2)
    ch = Challenge(
        user_id="u1", title="t", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0, ai_plan="[]",
    )
    base_goal = ladder_goal_day(ch)
    ch.ladder_adjust = '[{"day":3,"shift":2}]'
    shifted_goal = ladder_goal_day(ch)
    assert base_goal is not None and shifted_goal is not None
    assert shifted_goal == base_goal + 2


def test_lxz_shape_graduation_date() -> None:
    today = today_str()
    start = shift_date(today, -2)
    ch = Challenge(
        user_id="lxz", title="戒断挑战", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0, ai_plan="[]",
    )
    assert ladder_cap(ch, 1) == 12.0
    assert ladder_cap(ch, 3) == 11.0
    assert ladder_cap(ch, 5) == 10.0
    ch.ladder_adjust = '[{"day":3,"shift":2}]'
    assert ladder_cap(ch, 3) == 12.0
    assert ladder_cap(ch, 5) == 11.0
    assert ladder_cap(ch, 21) == 3.0


@pytest.mark.asyncio
async def test_assess_slip_episode_and_repeat() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        start = shift_date(today, -3)
        ch = _add_challenge(session,
            user_id="u1", title="戒烟", category="quit", task_type="counter", unit="根",
            direction="decrease", goal_type="soft", goal_rule="ladder",
            ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
            duration_days=66, start_date=start, end_date=shift_date(start, 65),
            status="active", target_value=1.0, ai_plan="[]")
        await session.flush()

        rows = _rows(ch, {shift_date(today, -1): 15.0, shift_date(today, -2): 7.0})
        slip = assess_slip(ch, rows, today)
        assert slip is not None
        assert slip["yesterday_cap"] == 11.0
        assert slip["over_amount"] == 4.0
        assert slip["episode_first"] is True
        assert slip["avoided_total"] == 5

        rows2 = _rows(ch, {shift_date(today, -1): 15.0, shift_date(today, -2): 13.0})
        slip2 = assess_slip(ch, rows2, today)
        assert slip2 is not None
        assert slip2["episode_first"] is False

        rows3 = _rows(ch, {shift_date(today, -1): 7.0})
        assert assess_slip(ch, rows3, today) is None
        assert assess_slip(ch, [], today) is None
    await engine.dispose()


@pytest.mark.asyncio
async def test_assess_slip_ignores_non_ladder_cap() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        start = shift_date(today, -2)
        ch = _add_challenge(session,
            user_id="u1", title="少刷手机", category="build", task_type="counter", unit="次",
            direction="decrease", goal_type="soft", goal_rule="fixed",
            duration_days=30, start_date=start, end_date=shift_date(start, 29),
            status="active", target_value=5.0, ai_plan="[]")
        await session.flush()
        rows = _rows(ch, {shift_date(today, -1): 9.0})
        assert assess_slip(ch, rows, today) is None
    await engine.dispose()
