from __future__ import annotations

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.infra.memory_client import add_memory, recall_memory
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.repositories.challenge_repository import ChallengeRepository
from app.services.ai_service import AIService

logger = get_logger("challengePlanet.checkin_bg")


async def generate_weekly_report_task(challenge_id: int) -> None:
    try:
        async with async_session() as session:
            challenge_repo = ChallengeRepository()
            challenge = await challenge_repo.get_by_id(session, challenge_id)
            if challenge is None:
                return
            checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
            checkin_data = [
                {
                    "day_number": c.day_number,
                    "mood": c.mood,
                    "reflection": c.reflection,
                    "value": c.value,
                    "timestamp": c.timestamp.isoformat(),
                }
                for c in checkins
            ]
            report = await AIService().generate_weekly_report(
                challenge.title, checkin_data, challenge.duration_days
            )
            await InsightRepository().create(session, {
                "challenge_id": challenge_id,
                "user_id": challenge.user_id,
                "insight_type": "weekly",
                "content": report,
            })
            await session.commit()
    except Exception as e:
        logger.warning("weekly report task failed: %s", e)


async def recall_context(user_id: str, title: str) -> str:
    memories = await recall_memory(user_id, f"{title} 打卡 心情")
    return "；".join(memories[:3])


async def safe_feedback(
    ai: AIService,
    title: str,
    day_number: int,
    total_days: int,
    mood: str,
    reflection: str,
    memory_context: str,
    value: float = 0.0,
    target: float = 0.0,
    direction: str = "increase",
    is_soft_exceeded: bool = False,
) -> str:
    try:
        return await ai.generate_daily_feedback(
            title, day_number, total_days, mood, reflection, memory_context,
            value=value, target=target, direction=direction,
            is_soft_exceeded=is_soft_exceeded,
        )
    except Exception as e:
        logger.warning("daily feedback fallback: %s", e)
        if is_soft_exceeded:
            return "这个时段对你来说特别难，我们一起想办法"
        return "坚持就是胜利！明天继续加油"


async def safe_declaration(ai: AIService, title: str, day_number: int) -> str:
    try:
        return await ai.generate_declaration(title, day_number, day_number)
    except Exception as e:
        logger.warning("declaration fallback: %s", e)
        return ""


async def save_memory(
    user_id: str, title: str, day_number: int,
    mood: str, reflection: str, value: float,
) -> None:
    mood_text = mood or "未记录"
    reflection_text = reflection or "无"
    await add_memory(
        user_id,
        f"挑战「{title}」第{day_number}天打卡：本次{value}，心情{mood_text}，心得{reflection_text}",
    )
