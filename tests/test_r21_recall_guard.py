from __future__ import annotations

import asyncio
import json
import os
import tempfile

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from nexus import audience

import app.models  # noqa: F401 register all tables
from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import AIInsight, CheckIn
from app.models.recall import RecallEvent
from app.services import recall_service
from app.services.journey_service import JourneyService, _silent_in_window
from app.services.mercy_service import load_valid_dates
from app.services.rescue_service import mark_rescue_sent, rescue_notify_due
from app.services.streak_service import (
    calc_streak,
    shift_date,
    silent_kept_of,
    today_str,
    trailing_kept_from_valid,
)

import pytest


# ---------- rescue 首发门槛 + 落痕 ----------

def test_rescue_first_notify_gate() -> None:
    today = today_str()
    assert rescue_notify_due(1, today) is False
    assert rescue_notify_due(2, today) is False
    assert rescue_notify_due(3, today) is True
    assert rescue_notify_due(5, "2026-10-19") is (int("20261019") % 2 == 0)


def test_mark_rescue_sent_persists_insight() -> None:
    async def main() -> AIInsight | None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await mark_rescue_sent(s, 7, "42", 3)
            row = (await s.execute(
                __import__("sqlalchemy").select(AIInsight)
                .where(AIInsight.insight_type == "rescue_care")
            )).scalar_one()
            await engine.dispose()
            return row

    row = asyncio.run(main())
    payload = json.loads(str(row.content))
    assert payload["missed_days"] == 3
    assert payload["date"] == today_str()


# ---------- 受众净化 guard ----------

def test_sendable_users_fail_open_on_fetch_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(ids: list[str]):
        return None

    monkeypatch.setattr(audience, "_fetch_statuses", boom)
    out = asyncio.run(audience.sendable_users({"1001", "2002"}))
    assert out == {"1001", "2002"}
    audience._status_cache.clear()


def test_sendable_users_filters_orphan_and_test(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(ids: list[str]):
        return {
            "1001": {"exists": True, "is_test": False, "disabled": False},
            "2002": {"exists": False, "is_test": False, "disabled": False},
            "3003": {"exists": True, "is_test": True, "disabled": False},
        }

    monkeypatch.setattr(audience, "_fetch_statuses", fake)
    out = asyncio.run(audience.sendable_users({"1001", "2002", "3003"}))
    assert out == {"1001"}
    audience._status_cache.clear()


def test_sendable_users_guard_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REMINDER_GUARD_OFF", "1")
    out = asyncio.run(audience.sendable_users({"1001"}))
    assert out == {"1001"}
    monkeypatch.delenv("REMINDER_GUARD_OFF")


# ---------- streak 缺席披露 ----------

def test_silent_kept_of_counts_unrecorded_valid_days() -> None:
    today = today_str()
    d = lambda n: shift_date(today, -n)  # noqa: E731
    valid = {d(1), d(2), d(3), d(4)}
    recorded = {d(1), d(3)}
    assert calc_streak(valid, today) == 4
    assert silent_kept_of(valid, recorded, today) == 2


def test_trailing_kept_from_valid_aligned_with_cap_fill() -> None:
    today = today_str()
    d = lambda n: shift_date(today, -n)  # noqa: E731
    start = d(6)
    valid = {d(1), d(2), d(3), d(5), d(6)}
    assert trailing_kept_from_valid(valid, today, start, shift_date(today, 30)) == 3
    full = {d(n) for n in range(1, 6)}
    assert trailing_kept_from_valid(full, today, start, shift_date(today, 30)) == 5
    assert trailing_kept_from_valid(set(), today, start, shift_date(today, 30)) == 0


def test_silent_in_window() -> None:
    today = today_str()
    d = lambda n: shift_date(today, -n)  # noqa: E731
    valid = {d(1), d(2), d(3)}
    recorded = {d(1)}
    assert _silent_in_window(valid, recorded, today, 3) == 2


# ---------- journey guard 口径对齐 ----------

def test_journey_build_guard_uses_cap_fill() -> None:
    async def main() -> dict[str, object]:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            today = today_str()
            start = shift_date(today, -7)
            ch = Challenge(
                user_id="42", title="戒断", status="active",
                direction="decrease", task_type="counter", goal_rule="ladder",
                goal_mode="ceiling", ladder_start=12.0, ladder_goal=3.0,
                ladder_interval=2, ladder_step=1.0, duration_days=40,
                start_date=start, end_date=shift_date(today, 33),
                target_value=12.0,
            )
            s.add(ch)
            await s.flush()
            from datetime import datetime

            from nexus.utils.time import TimeUtils

            s.add(CheckIn(
                challenge_id=ch.id, user_id="42", day_number=1,
                timestamp=TimeUtils.now_naive(), date=start, status="completed", value=5.0,
            ))
            await s.commit()
            block = await JourneyService().build(
                s, ch, 8, datetime.strptime(start, "%Y-%m-%d").date(),
                datetime.strptime(today, "%Y-%m-%d").date(),
            )
            valid = await load_valid_dates(s, ch.id)
            await engine.dispose()
            return {"block": block or {}, "valid": valid, "today": today, "start": start}

    out = asyncio.run(main())
    block: dict[str, object] = out["block"]
    valid: set[str] = out["valid"]
    today: str = out["today"]
    # 补齐口径：昨天往回的未超标日全 valid（无记录=守住）→ guard = 连续 valid 段
    expected = trailing_kept_from_valid(
        valid, today, out["start"], shift_date(today, 33),
    )
    assert block["guard_days"] == expected
    assert block["guard_days"] >= 6
    guard_ms = [m for m in block["milestones"] if str(m["key"]) == "guard_7"]
    assert guard_ms and guard_ms[0]["reached"] == (expected >= 7)
    assert block["guard_silent"] == max(0, block["guard_days"] - 1)


# ---------- recall 漏斗 ----------

def test_track_and_funnel() -> None:
    async def main() -> dict[str, object]:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            r1 = await recall_service.track_event(s, "42", 7, "absence", "arrived")
            r2 = await recall_service.track_event(s, "42", 7, "absence", "seen")
            r3 = await recall_service.track_event(s, "42", 7, "bad", "seen")
            r4 = await recall_service.track_event(s, "42", 7, "absence", "nope")
            assert r1["ok"] and r2["ok"]
            assert not r3["ok"] and not r4["ok"]
            funnel = await recall_service.build_funnel(s, days=7, user_id=None)
            await engine.dispose()
            return funnel

    funnel: dict[str, object] = asyncio.run(main())
    totals: dict[str, int] = funnel["event_totals"]
    assert totals.get("absence:arrived") == 1
    assert totals.get("absence:seen") == 1


def test_sent_date_of_slip_shifts_one_day() -> None:
    assert recall_service._sent_date_of(
        "slip_care", json.dumps({"date": "2026-10-10"}),
    ) == "2026-10-11"
    assert recall_service._sent_date_of(
        "absence_care", json.dumps({"date": "2026-10-13"}),
    ) == "2026-10-13"
