from __future__ import annotations

import asyncio
import os
import tempfile
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 register all tables
from app.db.database import Base
from app.models.points import ChallengeMeta
from app.services.mercy_service import _consume_bonus_mend, load_valid_dates
from app.services.return_service import (
    BACKFILL_TARGET_DAYS,
    grant_backfill_reward,
    return_state_of,
)
from app.services.streak_service import shift_date, today_str


def _challenge(start: str = "2026-10-01", target: float = 10.0) -> SimpleNamespace:
    return SimpleNamespace(
        start_date=start, target_value=target, unit="个", direction="increase",
        goal_rule="fixed", goal_type="hard", ladder_start=0, ladder_goal=0,
        ladder_interval=1, ladder_step=1,
    )


def _run(coro):
    return asyncio.run(coro)


def test_no_gap_no_return_state() -> None:
    today = today_str()
    ch = _challenge()
    valid = {shift_date(today, -1), shift_date(today, -2), shift_date(today, -3)}
    assert return_state_of(ch, valid, today) is None


def test_one_day_gap_is_normal_fluctuation() -> None:
    today = today_str()
    ch = _challenge()
    valid = {shift_date(today, -2)}
    assert return_state_of(ch, valid, today) is None


def test_return_day1_pre_checkin() -> None:
    """缺席 2 天后今天打开 app（尚未打卡）：回归页应在打卡前出现。"""
    today = today_str()
    ch = _challenge()
    valid = {shift_date(today, -3)}
    rs = return_state_of(ch, valid, today)
    assert rs is not None
    assert rs["gap_days"] == 2
    assert rs["return_day"] == 1
    assert rs["walked_days"] == 1
    assert rs["micro_target"] == 2


def test_return_day1_post_checkin() -> None:
    today = today_str()
    ch = _challenge()
    valid = {shift_date(today, -4), today}
    rs = return_state_of(ch, valid, today)
    assert rs is not None
    assert rs["gap_days"] == 3
    assert rs["return_day"] == 1


def test_return_day3_window_and_day4_exits() -> None:
    """缺口后连回来 3 天在第 3 天展示；第 4 天（或缺口不足 2 天）退出窗口。"""
    today = today_str()
    ch = _challenge()
    valid3 = {shift_date(today, -5), shift_date(today, -2), shift_date(today, -1), today}
    rs = return_state_of(ch, valid3, today)
    assert rs is not None
    assert rs["gap_days"] == 2
    assert rs["return_day"] == 3
    valid4 = valid3 | {shift_date(today, -4)}
    assert return_state_of(ch, valid4, today) is None


def test_absent_user_in_app_gets_return_hero() -> None:
    """在场即回归：缺席中的人打开 app（尚未打卡）=回归第 1 天，回归页接管缺席卡。"""
    today = today_str()
    ch = _challenge()
    valid = {shift_date(today, -5)}
    rs = return_state_of(ch, valid, today)
    assert rs is not None
    assert rs["gap_days"] == 4
    assert rs["return_day"] == 1


@pytest.fixture()
def session_factory():
    def _make():
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return engine, Session

    return _make


def test_backfill_reward_once_per_episode(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> tuple[bool, bool, ChallengeMeta | None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            first = await grant_backfill_reward(s, 33, "2026-10-10")
            await s.flush()
            second = await grant_backfill_reward(s, 33, "2026-10-10")
            await s.flush()
            meta = (await s.execute(select(ChallengeMeta).where(ChallengeMeta.challenge_id == 33))).scalar_one_or_none()
            await engine.dispose()
            return first, second, meta

    first, second, meta = _run(main())
    assert first is True
    assert second is False, "同 episode 只发一次"
    assert meta is not None
    import json

    extra = json.loads(str(meta.extra))
    assert extra["bonus_mends"] == 1
    assert extra["backfill_episode"] == "2026-10-10"


def test_backfill_new_episode_rewards_again(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> bool:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await grant_backfill_reward(s, 33, "2026-10-10")
            await s.flush()
            again = await grant_backfill_reward(s, 33, "2026-10-20")
            await engine.dispose()
            return again

    assert _run(main()) is True


def test_bonus_mend_consumption(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await grant_backfill_reward(s, 44, "2026-10-10")
            await _consume_bonus_mend(s, 44)
            from app.services.return_service import bonus_mends_of

            left = await bonus_mends_of(s, 44)
            await _consume_bonus_mend(s, 44)
            await _consume_bonus_mend(s, 44)
            floor = await bonus_mends_of(s, 44)
            await engine.dispose()
            assert floor == 0, "不得扣成负数"
            return left

    assert _run(main()) == 0
