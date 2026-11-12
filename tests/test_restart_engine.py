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


@pytest.mark.asyncio
async def test_micro_target_uses_today_cap_not_day1() -> None:
    """回归 micro（今天先做最小的）必须相对今日 cap，不是 day1 起点——
    decrease 阶梯今日 cap < day1，day1 口径会把「最小的一步」说大（r27 遗留②）。"""
    from app.services.return_service import return_state_of

    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)  # start 12→goal 3，今日（day35）cap 已到 3
        await session.commit()
        today = today_str()
        from datetime import datetime as _dt
        start = _dt.strptime(str(ch.start_date), "%Y-%m-%d").date()
        _t = _dt.strptime(today, "%Y-%m-%d").date()
        day_number = (_t - start).days + 1
        today_cap = daily_target(ch, day_number)
        assert today_cap < 12.0
        micro = max(1, round(today_cap / 5))
        # 旧实现（day1 口径）给 12/5=2；新实现必须等于今日 cap 口径
        state = _return_state_via_private(ch, today)
        assert state is not None
        assert int(state["micro_target"]) == micro


def _return_state_via_private(ch, today: str) -> dict[str, object] | None:
    from datetime import datetime as _dt

    from app.services.return_service import return_state_of

    start = _dt.strptime(str(ch.start_date), "%Y-%m-%d").date()
    t = _dt.strptime(today, "%Y-%m-%d").date()
    # 回归窗：今天未打卡、昨天缺、前天缺 → gap 从 first_missing 起算；start 到 today-2 有「记录」
    recorded = set()
    walk = start
    while walk <= t:
        recorded.add(walk.isoformat())
        walk = __import__("datetime").timedelta(days=1) + walk
    recorded.discard(shift_date(today, -1))
    recorded.discard(shift_date(today, -2))
    return return_state_of(ch, set(recorded), today, recorded_dates=recorded)


@pytest.mark.asyncio
async def test_today_payload_ladder_start_reflects_anchor() -> None:
    """重锚后 today 透出的阶梯起点必须是锚点 cap（r27 遗留③：任务卡徽章「12→3」
    语义过期，重锚后应为「7→3」），并带 restarted 标志。"""
    import json as _json

    from app.services.challenge_present import build_today_payload

    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.commit()
        today = today_str()
        anchor_day = _day_number(ch, today)
        payload = build_today_payload(
            ch, int(ch.id), anchor_day, today, {}, [], 0.0, 3.0, 3.0,
            {"streak": 0, "completed_days": 0, "total_days": 66, "last_streak": 0}, 0.0,
        )
        assert payload["ladder_start"] == 12.0
        assert not payload.get("restarted")
        ch.ladder_restart = _json.dumps({"date": today, "cap": 7})
        payload = build_today_payload(
            ch, int(ch.id), anchor_day, today, {}, [], 0.0, 7.0, 7.0,
            {"streak": 0, "completed_days": 0, "total_days": 66, "last_streak": 0}, 0.0,
        )
        assert payload["ladder_start"] == 7.0
        assert payload["ladder_goal"] == 3.0
        assert payload.get("restarted") is True


@pytest.mark.asyncio
async def test_ladder_progress_pct_rebased_after_anchor() -> None:
    """重锚后进度百分比按锚点新曲线重算——否则 cap 回升会算出「进度倒退」。"""
    from app.services.goal_rule_service import ladder_progress_pct

    engine, maker = await _make_session()
    async with maker() as session:
        ch = _ladder_challenge(session)
        await session.commit()
        today = today_str()
        anchor_day = _day_number(ch, today)
        before = ladder_progress_pct(ch, anchor_day)
        ch.ladder_restart = json.dumps({"date": today, "cap": 7})
        after = ladder_progress_pct(ch, anchor_day)
        assert after < before
        assert after == 0.0
