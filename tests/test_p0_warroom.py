from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.datetime_utils import now_china
from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.models.points import ChallengeMeta
from app.repositories.points_repository import ChallengeMetaRepository, StreakActionRepository
from app.services.goal_rule_service import (
    ensure_ladder_direction,
    ladder_progress_pct,
)
from app.services.mercy_service import MercyService
from app.services.streak_service import shift_date, today_str


class _Ch:
    def __init__(self, direction: str) -> None:
        self.direction = direction
        self.goal_rule = "ladder"
        self.ladder_start = 2.0
        self.ladder_goal = 5.0
        self.ladder_interval = 2
        self.ladder_step = 1.0
        self.ladder_adjust = None
        self.ladder_restart = None
        self.start_date = shift_date(today_str(), -10)
        self.target_value = 2.0


def test_ladder_progress_pct_increase_returns_float() -> None:
    ch = _Ch("increase")
    pct = ladder_progress_pct(ch, 1)
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_ladder_progress_pct_decrease_still_works() -> None:
    ch = _Ch("decrease")
    ch.ladder_goal = 0.0
    pct = ladder_progress_pct(ch, 1)
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_ensure_ladder_direction_rejects_increase() -> None:
    with pytest.raises(ValueError):
        ensure_ladder_direction("increase", "ladder")


def test_ensure_ladder_direction_allows_decrease() -> None:
    ensure_ladder_direction("decrease", "ladder")
    ensure_ladder_direction("increase", "fixed")
    ensure_ladder_direction("", "")


async def _mercy_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    today = today_str()
    d2 = shift_date(today, -2)
    ch = Challenge(
        user_id="u1", title="打卡挑战", category="fitness", task_type="counter", unit="次",
        direction="increase", goal_type="hard", goal_rule="fixed", goal_mode="auto",
        duration_days=30, status="active",
        target_value=1.0, ai_plan="[]", share_token="t-mercy", color="#10b981", icon="✅",
        start_date=shift_date(today, -5), end_date=shift_date(today, 24),
    )
    session.add(ch)
    await session.flush()
    session.add(CheckIn(
        challenge_id=ch.id, user_id="u1", day_number=4, status="completed",
        timestamp=now_china(), date=d2, value=1.0, unit="次",
        target_value=1.0, goal_type="hard", direction="increase", completion_pct=100.0,
    ))
    session.add(ChallengeMeta(challenge_id=ch.id, extra=json.dumps({"shields": 2})))
    await session.commit()
    return engine, session, ch, today


@pytest.mark.asyncio
async def test_get_mercy_status_is_readonly() -> None:
    engine, session, ch, today = await _mercy_fixture()
    try:
        first = await MercyService().get_mercy_status(session, ch.id, "u1")
        second = await MercyService().get_mercy_status(session, ch.id, "u1")
        assert first == second
        assert first["shields"] == 2
        assert first["shield_activated"] is False
        actions = await StreakActionRepository().get_by_challenge(session, ch.id)
        assert actions == []
        meta = await ChallengeMetaRepository().get(session, ch.id)
        assert json.loads(meta.extra)["shields"] == 2
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_settle_shield_on_return_consumes_once() -> None:
    engine, session, ch, today = await _mercy_fixture()
    service = MercyService()
    try:
        left = await service.settle_shield_on_return(session, ch, "u1")
        assert left == 1
        actions = await StreakActionRepository().get_by_challenge(session, ch.id)
        assert [a.action_date for a in actions] == [shift_date(today, -1)]
        meta = await ChallengeMetaRepository().get(session, ch.id)
        assert json.loads(meta.extra)["shields"] == 1
        left_again = await service.settle_shield_on_return(session, ch, "u1")
        assert left_again == 1
        actions = await StreakActionRepository().get_by_challenge(session, ch.id)
        assert len(actions) == 1
    finally:
        await session.close()
        await engine.dispose()
