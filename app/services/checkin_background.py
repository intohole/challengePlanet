from __future__ import annotations

import asyncio
from datetime import datetime

from nexus.logging import get_logger

from app.infra.memory_client import add_memory, recall_memory
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.ai_service import AIService

logger = get_logger("challengePlanet.checkin_bg")

_background_tasks: set[asyncio.Task] = set()


def fire_and_forget(coro: object) -> None:
    task = asyncio.create_task(coro)  # type: ignore[arg-type]
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def recall_context(user_id: str, title: str) -> str:
    memories = await recall_memory(user_id, f"{title} 打卡 心情")
    return "；".join(memories[:3])


async def build_feedback_prompt_inputs(
    session: object, checkin: CheckIn, challenge: Challenge
) -> dict[str, object]:
    memory_context = await recall_context(checkin.user_id, challenge.title)
    is_soft_exceeded = bool(
        checkin.target_value and checkin.value
        and float(checkin.value) > float(checkin.target_value)
        and getattr(checkin, "goal_type", "hard") == "soft"
    )
    return {
        "challenge_title": challenge.title,
        "day_number": checkin.day_number,
        "total_days": challenge.duration_days,
        "mood": checkin.mood,
        "reflection": checkin.reflection,
        "memory_context": memory_context,
        "value": float(checkin.value or 0),
        "target": float(checkin.target_value or 0),
        "direction": str(challenge.direction or "increase"),
        "is_soft_exceeded": is_soft_exceeded,
        "journey_context": await journey_context_for(session, challenge, checkin),
    }


async def journey_context_for(session: object, challenge: Challenge, checkin: CheckIn) -> str:
    from app.core.datetime_utils import now_china
    from app.services.journey_service import JourneyService, journey_prompt_line

    try:
        start = datetime.strptime(str(challenge.start_date)[:10], "%Y-%m-%d").date()
    except Exception:
        return ""
    try:
        journey = await JourneyService().build(
            session, challenge, max(1, int(checkin.day_number or 1)), start, now_china().date(),
        )
        return journey_prompt_line(journey)
    except Exception as e:
        logger.warning("journey context fallback: %s", e)
        return ""


def feedback_fallback(day_number: int, mood: str, is_soft_exceeded: bool) -> str:
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
