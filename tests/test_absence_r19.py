from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import AIInsight, CheckIn
from app.services.absence_service import (
    ABSENCE_CARE_INSIGHT,
    absence_care_text,
    absence_due,
    assess_absence,
    collect_absence_items,
    mark_absence_sent,
    same_episode_cared,
    touch_sent_date,
)
from app.services.slip_service import SLIP_CARE_INSIGHT
from app.services.streak_service import shift_date, today_str


def _day_num(start: str, date_str: str) -> int:
    from datetime import date as _d
    return (_d.fromisoformat(date_str) - _d.fromisoformat(start)).days + 1


def _ladder_challenge(**kw) -> Challenge:
    today = today_str()
    start = kw.pop("start_date", shift_date(today, -4))
    base = dict(
        user_id="u1", title="戒断挑战", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0, ai_plan="[]",
    )
    base.update(kw)
    return Challenge(**base)


def _rows(values: dict[str, float]) -> list[dict]:
    return [
        {"date": d, "value": v, "checkin_count": 1}
        for d, v in sorted(values.items())
    ]


def test_assess_absence_core_matrix() -> None:
    today = today_str()
    ch = _ladder_challenge()
    d1 = shift_date(today, -3)

    miss = assess_absence(ch, _rows({d1: 6.0}), today)
    assert miss is not None
    assert miss["absent_days"] == 2
    assert miss["last_record_date"] == d1
    assert miss["last_value"] == 6.0
    assert miss["cap_now"] == 10.0
    assert miss["avoided_total"] == 6
    assert miss["suggest_adjust"] is False

    over = assess_absence(ch, _rows({d1: 15.0}), today)
    assert over is not None
    assert over["suggest_adjust"] is True
    assert over["absent_days"] == 2

    long_miss = assess_absence(ch, _rows({d1: 6.0}), shift_date(today, 2))
    assert long_miss is not None
    assert long_miss["absent_days"] == 4


def test_assess_absence_negative_paths() -> None:
    today = today_str()
    ch = _ladder_challenge()
    d1, d2, d3 = shift_date(today, -3), shift_date(today, -2), shift_date(today, -1)

    assert assess_absence(ch, _rows({d3: 5.0}), today) is None
    assert assess_absence(ch, _rows({d1: 5.0, d3: 5.0}), today) is None
    assert assess_absence(ch, _rows({d1: 5.0, d2: 5.0, d3: 5.0}), today) is None
    assert assess_absence(ch, [], today) is None

    rows_with_today = _rows({d1: 5.0})
    rows_with_today.append({"date": today, "value": 2.0, "checkin_count": 1})
    assert assess_absence(ch, rows_with_today, today) is None

    fixed = _ladder_challenge(goal_rule="fixed", ladder_start=0.0, ladder_goal=0.0)
    assert assess_absence(fixed, _rows({d1: 9.0}), today) is None

    fresh = _ladder_challenge(start_date=shift_date(today, -1))
    assert assess_absence(fresh, [], today) is None


def test_absence_due_touch_gap() -> None:
    today = today_str()
    assert absence_due({}, today) is True
    assert absence_due({ABSENCE_CARE_INSIGHT: shift_date(today, -3)}, today) is True
    assert absence_due({ABSENCE_CARE_INSIGHT: shift_date(today, -1)}, today) is False
    assert absence_due({ABSENCE_CARE_INSIGHT: shift_date(today, -2)}, today) is True
    slip_sent = touch_sent_date(SLIP_CARE_INSIGHT, {"date": shift_date(today, -2)})
    assert slip_sent == shift_date(today, -1)
    assert absence_due({SLIP_CARE_INSIGHT: slip_sent}, today) is False
    slip_sent_old = touch_sent_date(SLIP_CARE_INSIGHT, {"date": shift_date(today, -4)})
    assert absence_due({SLIP_CARE_INSIGHT: slip_sent_old}, today) is True


def test_touch_sent_date_shifts_slip_only() -> None:
    today = today_str()
    assert touch_sent_date(SLIP_CARE_INSIGHT, {"date": today}) == shift_date(today, 1)
    assert touch_sent_date(ABSENCE_CARE_INSIGHT, {"date": today}) == today
    assert touch_sent_date(SLIP_CARE_INSIGHT, {"nope": 1}) is None
    assert touch_sent_date(SLIP_CARE_INSIGHT, "bad") is None


def test_absence_care_text_no_shaming_words() -> None:
    today = today_str()
    ch = _ladder_challenge()
    miss = assess_absence(ch, _rows({shift_date(today, -3): 6.0}), today)
    assert miss is not None
    title, body = absence_care_text("戒断挑战", "根", miss)
    assert title == "「戒断挑战」2 天没见了"
    for banned in ("超了", "断了", "破戒", "失败"):
        assert banned not in body
    assert "10" in body and "6" in body


@pytest.mark.asyncio
async def test_same_episode_cared_and_mark() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        ch = _ladder_challenge()
        session.add(ch)
        await session.flush()
        assert await same_episode_cared(session, ch.id, "2026-10-08") is False
        await mark_absence_sent(session, ch.id, "u1", {
            "absent_days": 2, "last_record_date": "2026-10-08",
        })
        await session.flush()
        assert await same_episode_cared(session, ch.id, "2026-10-08") is True
        assert await same_episode_cared(session, ch.id, "2026-10-10") is False
        row = await session.get(AIInsight, 1)
        assert row.insight_type == ABSENCE_CARE_INSIGHT
        assert '"last_record_date": "2026-10-08"' in row.content
    await engine.dispose()


@pytest.mark.asyncio
async def test_collect_absence_items_end_to_end() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        today = today_str()
        ch = _ladder_challenge()
        session.add(ch)
        await session.flush()
        session.add(CheckIn(
            challenge_id=ch.id, user_id="u1", day_number=1,
            status="completed", timestamp=datetime.fromisoformat(shift_date(today, -3) + "T10:00:00"),
            date=shift_date(today, -3), value=6.0, unit="根", target_value=12.0,
        ))
        await session.flush()
        items = await collect_absence_items(session, [ch])
        assert len(items) == 1
        payload = items[0]["payload"]
        assert payload["title"] == "「戒断挑战」2 天没见了"
        assert payload["link"] == f"/challengePlanet/?ch={ch.id}&rc=absence"
        assert payload["channels"] == ["in_app", "email"]
        assert items[0]["absence"]["suggest_adjust"] is False

        await mark_absence_sent(session, ch.id, "u1", items[0]["absence"])
        await session.flush()
        assert await collect_absence_items(session, [ch]) == []
    await engine.dispose()
