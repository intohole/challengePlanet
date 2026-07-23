from __future__ import annotations

import json

from nexus.logging import get_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.models.adaptive import AdaptiveSuggestion
from app.repositories.adaptive_repository import AdaptiveRepository
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.ai_service import AIService
from app.services.streak_service import day_number_of, today_str

logger = get_logger("challengePlanet.adaptive")

BAD_MOOD_STREAK_THRESHOLD = 2


def fallback_light_task(task: dict[str, object], day: int, mode: str = "lighten") -> dict[str, object]:
    base_title = str(task.get("title", "") or "今日任务")
    base_desc = str(task.get("description", "") or "")
    if mode == "micro":
        return {
            "day": day,
            "title": base_title,
            "description": f"今天只做5分钟最小一步：{base_desc[:30] or base_title}",
            "tip": "微行动也算数，完成比完美重要",
        }
    return {
        "day": day,
        "title": base_title,
        "description": f"轻松版：{base_desc[:40] or base_title}（做到一半就算赢）",
        "tip": "状态不好时，减负是为了走得更远",
    }


class AdaptiveService:
    def __init__(self) -> None:
        self._repo = AdaptiveRepository()
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._ai = AIService()

    async def get_pending(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> AdaptiveSuggestion | None:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        suggestion = await self._repo.get_pending(session, challenge_id)
        if suggestion is None:
            return None
        current_day = day_number_of(challenge.start_date, today_str())
        if suggestion.target_day <= current_day or suggestion.target_day > challenge.duration_days:
            await self._repo.update_status(session, suggestion, "expired")
            return None
        return suggestion

    async def respond(
        self, session: AsyncSession, suggestion_id: int, user_id: str, accept: bool
    ) -> dict[str, object]:
        suggestion = await self._repo.get_by_id(session, suggestion_id)
        if suggestion is None or suggestion.user_id != user_id or suggestion.status != "pending":
            raise ValueError("建议不存在或已处理")
        if not accept:
            await self._repo.update_status(session, suggestion, "rejected")
            return {"ok": True, "applied": False}

        challenge = await self._challenge_repo.get_by_id(session, suggestion.challenge_id)
        if challenge is None:
            raise ValueError("挑战不存在")
        try:
            plan = json.loads(challenge.ai_plan) if challenge.ai_plan else []
        except json.JSONDecodeError:
            plan = []
        task = json.loads(suggestion.task_json)
        idx = suggestion.target_day - 1
        if 0 <= idx < len(plan):
            task["day"] = suggestion.target_day
            plan[idx] = task
            challenge.ai_plan = json.dumps(plan, ensure_ascii=False)
            await session.flush()
        await self._repo.update_status(session, suggestion, "accepted")
        return {"ok": True, "applied": True, "task": task}


async def evaluate_after_bad_mood_task(challenge_id: int) -> None:
    try:
        async with async_session() as session:
            challenge = await ChallengeRepository().get_by_id(session, challenge_id)
            if challenge is None or challenge.status != "active":
                return
            checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
            recent = [c for c in checkins if c.mood][-BAD_MOOD_STREAK_THRESHOLD:]
            if len(recent) < BAD_MOOD_STREAK_THRESHOLD:
                return
            if not all(c.mood == "bad" for c in recent):
                return
            repo = AdaptiveRepository()
            if await repo.get_pending(session, challenge_id) is not None:
                return
            current_day = day_number_of(challenge.start_date, today_str())
            target_day = current_day + 1
            if target_day > challenge.duration_days:
                return
            try:
                plan = json.loads(challenge.ai_plan) if challenge.ai_plan else []
            except json.JSONDecodeError:
                plan = []
            original = plan[target_day - 1] if 0 <= target_day - 1 < len(plan) else {}
            ai = AIService()
            task: dict[str, object] | None = None
            if original:
                adjusted = await ai.generate_adjusted_tasks(challenge.title, [original], "lighten")
                if adjusted:
                    task = adjusted[0]
                    task["day"] = target_day
            if task is None:
                task = fallback_light_task(original, target_day)
            try:
                await repo.create(session, {
                    "challenge_id": challenge_id,
                    "user_id": challenge.user_id,
                    "kind": "lighten",
                    "reason": "注意到你最近连续几天都觉得有点吃力，这说明计划在推你的极限——好事，但别绷断。已为明天准备了一个减负版任务，保住节奏比完成任务量更重要。",
                    "task_json": json.dumps(task, ensure_ascii=False),
                    "target_day": target_day,
                    "status": "pending",
                })
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return
            logger.info("adaptive lighten suggestion created: challenge=%s day=%s", challenge_id, target_day)
    except Exception as e:
        logger.warning("adaptive evaluate task failed: %s", e)
