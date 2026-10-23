"""S41 数据完整性守底：challenge 删除级联六表零残留（孤儿防线钉死）。

判例：本地库 ai_insights 10/challenge_meta 30/streak_actions 2 孤儿系历史 e2eclean
直删 challenges 绕过级联；delete_with_children 六表级联在位（challenge_repository.py:44），
本守底防级联被拆分/重构时静默丢表。
"""
from __future__ import annotations

import asyncio
import os
import tempfile

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import AIInsight, CheckIn, WeightRecord
from app.models.points import ChallengeMeta, StreakAction
from app.models.adaptive import AdaptiveSuggestion
from app.repositories.challenge_repository import ChallengeRepository

import app.models.archive  # noqa: F401,F811 register table


def _mk_challenge(uid: str) -> Challenge:
    return Challenge(
        user_id=uid, title="S41级联守底", description="", category="quit",
        task_type="counter", target_value=10.0, unit="根", direction="decrease",
        goal_type="hard", decompose_mode="none", duration_days=30,
        start_date="2026-10-01", end_date="2026-10-31", status="active",
        ai_plan="[]", color="#ef4444", icon="🚭", scene_template="",
        is_shared=False, share_token="s" * 32,
        goal_rule="ladder", goal_mode="ceiling",
        ladder_start=10.0, ladder_goal=5.0, ladder_interval=2, ladder_step=1.0,
    )


async def _run() -> None:
    with tempfile.TemporaryDirectory() as td:
        engine = create_async_engine(f"sqlite+aiosqlite:///{td}/s41.db")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        repo = ChallengeRepository()
        async with Session() as session:
            ch = _mk_challenge("s41-user")
            session.add(ch)
            await session.flush()
            cid = int(ch.id)
            session.add_all([
                CheckIn(challenge_id=cid, user_id="s41-user", day_number=1, date="2026-10-24", status="done", timestamp=datetime(2026, 10, 24, 8, 0, 0)),
                AIInsight(challenge_id=cid, user_id="s41-user", insight_type="daily", content="x"),
                WeightRecord(challenge_id=cid, user_id="s41-user", date="2026-10-24", weight_kg=70.0),
                StreakAction(challenge_id=cid, user_id="s41-user", action="break", action_date="2026-10-24"),
                ChallengeMeta(challenge_id=cid, source="s41"),
                AdaptiveSuggestion(challenge_id=cid, user_id="s41-user", kind="daily",
                                   reason="x", task_json="{}", target_day=1, status="pending"),
            ])
            await session.commit()
            for model in (CheckIn, AIInsight, WeightRecord, StreakAction, ChallengeMeta, AdaptiveSuggestion):
                n = len((await session.execute(select(model).where(model.challenge_id == cid))).scalars().all())
                assert n == 1, f"{model.__tablename__} 造数失败"
            await repo.delete_with_children(session, cid)
            await session.commit()
            for model in (CheckIn, AIInsight, WeightRecord, StreakAction, ChallengeMeta, AdaptiveSuggestion):
                n = len((await session.execute(select(model).where(model.challenge_id == cid))).scalars().all())
                assert n == 0, f"{model.__tablename__} 删除级联残留 {n} 行（孤儿回潮）"
            gone = (await session.execute(select(Challenge).where(Challenge.id == cid))).scalar_one_or_none()
            assert gone is None
        await engine.dispose()


def test_delete_with_children_cascades_all_six() -> None:
    asyncio.run(_run())
