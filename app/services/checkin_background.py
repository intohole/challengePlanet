from __future__ import annotations

from nexus.logging import get_logger

from app.db.database import async_session
from app.infra.memory_client import add_memory, recall_memory
from app.repositories.checkin_repository import CheckInRepository
from app.services.ai_service import AIService

logger = get_logger("challengePlanet.checkin_bg")


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
        prefix = f"第{day_number}天的记录已收到，"
        if is_soft_exceeded:
            if mood == "bad":
                return "没关系，记录本身就是进步"
            return f"{prefix}超出目标不着急，先记下来，我们下次一起想办法"
        if mood == "bad":
            return "今天辛苦了，能记下来就已经很了不起了"
        return f"{prefix}保持自己的节奏，明天继续"


async def safe_declaration(ai: AIService, title: str, day_number: int) -> str:
    try:
        return await ai.generate_declaration(title, day_number, day_number)
    except Exception as e:
        logger.warning("declaration fallback: %s", e)
        return ""


async def fill_ai_after_checkin(
    checkin_id: int,
    user_id: str,
    title: str,
    day_number: int,
    total_days: int,
    mood: str,
    reflection: str,
    value: float,
    target: float,
    direction: str,
    is_soft_exceeded: bool,
) -> None:
    try:
        async with async_session() as session:
            checkin = await CheckInRepository().get_by_id(session, checkin_id)
            if checkin is None:
                return
            ai = AIService()
            memory_context = await recall_context(user_id, title)
            feedback = await safe_feedback(
                ai, title, day_number, total_days, mood, reflection, memory_context,
                value=value, target=target, direction=direction,
                is_soft_exceeded=is_soft_exceeded,
            )
            declaration = await safe_declaration(ai, title, day_number)
            await CheckInRepository().update(session, checkin, {
                "ai_feedback": feedback, "declaration": declaration,
            })
            await session.commit()
    except Exception as e:
        logger.warning("async ai fill failed: %s", e)


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
