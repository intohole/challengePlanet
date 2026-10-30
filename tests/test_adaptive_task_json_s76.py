from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.adaptive import AdaptiveSuggestion
from app.models.challenge import Challenge
from app.services.adaptive_service import AdaptiveService
from app.services.streak_service import shift_date, today_str


def _challenge_row() -> Challenge:
    today = today_str()
    start = shift_date(today, -4)
    return Challenge(
        user_id="u1", title="测试挑战", category="study", task_type="counter", unit="页",
        direction="increase", goal_type="soft", goal_rule="fixed",
        duration_days=30, start_date=start, end_date=shift_date(start, 29),
        status="active", target_value=1.0,
        ai_plan='[{"day": 1, "task": "阅读", "amount": 10}]',
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "task_json,expect_error",
    [
        (None, "建议的任务数据无效"),
        ("{broken json", "建议的任务数据无效"),
        ('{"task": "复习"}', None),
    ],
)
async def test_respond_bad_task_json_fail_explicit(task_json: str | None, expect_error: str | None) -> None:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        challenge = _challenge_row()
        session.add(challenge)
        await session.flush()
        sug = AdaptiveSuggestion(
            user_id="u1", challenge_id=challenge.id, target_day=1,
            task_json=task_json, reason="test", status="pending",
        )
        session.add(sug)
        await session.commit()
        service = AdaptiveService()

        if expect_error:
            with pytest.raises(ValueError, match=expect_error):
                await service.respond(session, sug.id, "u1", accept=True)
        else:
            result = await service.respond(session, sug.id, "u1", accept=True)
            assert result["ok"] is True
            assert result["applied"] is True
            assert result["task"]["task"] == "复习"
    await engine.dispose()
