from __future__ import annotations

import json
import random

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.chatkit.models import ChatConversation
from app.core.datetime_utils import now_china
from app.db.database import Base
from app.db.database import db_manager as app_db_manager
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.models.points import ChallengeMeta
from app.repositories.points_repository import ChallengeMetaRepository, StreakActionRepository
from app.schemas.checkin import CheckInCreate
from app.services.goal_rule_service import (
    ensure_ladder_direction,
    ladder_progress_pct,
)
from app.services.mercy_service import MercyService
from app.services.points_service import (
    DAILY_EARN_CAP_PER_CHALLENGE,
    PointsService,
)
from app.services.streak_service import shift_date, today_str


class _Ch:
    def __init__(self, direction: str) -> None:
        self.direction = direction
        self.goal_rule = "ladder"
        self.task_type = "counter"
        self.unit = "根"
        self.goal_type = "soft"
        self.decompose_mode = "none"
        self.duration_days = 66
        self.end_date = shift_date(today_str(), 55)
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


def test_build_today_payload_increase_ladder_no_crash() -> None:
    from app.services.challenge_present import build_today_payload

    ch = _Ch("increase")
    payload = build_today_payload(
        ch, 1, 1, today_str(),
        task={"task_type": "counter"}, today_checkins=[], today_total=0.0,
        today_target=2.0, dynamic_baseline=0.0,
        stats={"streak": 0, "silent_kept": 0, "completed_days": 0}, progress=0.0,
    )
    assert payload["challenge_id"] == 1
    assert isinstance(payload.get("ladder_progress_pct"), float)


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


def test_app_db_manager_enables_sqlite_pragma() -> None:
    assert app_db_manager._config_arg.database.sqlite_pragma is True


def test_checkin_schema_rejects_negative_value() -> None:
    with pytest.raises(Exception):
        CheckInCreate(value=-5.0)


def test_checkin_schema_rejects_oversize_value() -> None:
    with pytest.raises(Exception):
        CheckInCreate(value=99999.0)


def test_weekly_prompt_has_no_time_slot_fabrication() -> None:
    from app.services.prompts import WEEKLY_SYSTEM

    assert "时段" not in WEEKLY_SYSTEM


def test_milestone_tips_no_fabricated_percentile() -> None:
    from app.services.guidance_service import MILESTONE_TIPS

    for tip in MILESTONE_TIPS.values():
        assert "超越" not in tip
        assert "%" not in tip


def test_encouragement_no_fabricated_percentile() -> None:
    from app.services.guidance_service import GuidanceService

    svc = GuidanceService()
    for completed, streak in ((3, 3), (30, 10), (66, 20), (5, 0), (0, 0)):
        text = svc._build_encouragement(completed, streak)
        assert "超越" not in text
        assert "%" not in text


async def _points_fixture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, maker()


@pytest.mark.asyncio
async def test_award_checkin_daily_cap_per_challenge() -> None:
    engine, session = await _points_fixture()
    try:
        svc = PointsService(rng=random.Random(7))
        earned = 0
        for _ in range(12):
            base, chest = await svc.award_checkin(session, "u1", 1, 3, completion_pct=100.0)
            earned += base + chest
        assert earned <= DAILY_EARN_CAP_PER_CHALLENGE
        base_other, chest_other = await svc.award_checkin(session, "u1", 2, 3, completion_pct=100.0)
        assert base_other > 0
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_pragma_wires_wal(tmp_path) -> None:
    from nexus import DatabaseManager
    from nexus.config import DatabaseConfig, NexusConfig

    mgr = DatabaseManager(
        NexusConfig(
            database=DatabaseConfig(
                url=f"sqlite+aiosqlite:///{tmp_path}/p0wal.db",
                echo=False,
                sqlite_pragma=True,
            )
        )
    )
    try:
        await mgr.init()
        async with mgr.engine.connect() as conn:
            row = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
        assert str(row).lower() == "wal"
    finally:
        await mgr.engine.dispose()


async def _purge_fixture():
    import app.chatkit.models  # noqa: F401
    from app.chatkit.models import ChatBase
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(ChatBase.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    session = maker()
    today = today_str()
    ch = Challenge(
        user_id="u1", title="清理挑战", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="fixed", goal_mode="auto",
        duration_days=30, status="active", target_value=1.0, ai_plan="[]",
        share_token="t-purge", color="#ef4444", icon="🚭",
        start_date=shift_date(today, -5), end_date=shift_date(today, 24),
    )
    session.add(ch)
    await session.flush()
    session.add_all([
        ChatConversation(user_id="u1", app_name="challengePlanet", meta={"challenge_id": ch.id}),
        ChatConversation(user_id="u1", app_name="challengePlanet", meta={"challenge_id": 999}),
        ChatConversation(user_id="u1", app_name="challengePlanet", meta={}),
        ChatConversation(user_id="u1", app_name="otherapp", meta={"challenge_id": ch.id}),
    ])
    await session.commit()
    return engine, session, ch


@pytest.mark.asyncio
async def test_purge_cascades_chat_conversations() -> None:
    from app.repositories.challenge_repository import ChallengeRepository

    engine, session, ch = await _purge_fixture()
    try:
        await ChallengeRepository().delete_with_children(session, ch.id)
        rows = (await session.execute(text("SELECT app_name, meta FROM chat_conversations"))).all()
        assert len(rows) == 3
        own = [m for app, m in rows if app == "challengePlanet"]
        assert own
        metas = [json.loads(m) if isinstance(m, str) else (m or {}) for m in own]
        assert all(item.get("challenge_id") != ch.id for item in metas)
        assert any(app == "otherapp" for app, _ in rows)
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_purge_tolerates_missing_chat_table() -> None:
    from app.repositories.challenge_repository import ChallengeRepository

    engine, session, ch = await _purge_fixture()
    try:
        await session.execute(text("DROP TABLE chat_conversations"))
        await session.commit()
        await ChallengeRepository().delete_with_children(session, ch.id)
    finally:
        await session.close()
        await engine.dispose()
