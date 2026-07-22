from __future__ import annotations

import asyncio
from datetime import datetime

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.infra.memory_client import add_memory, recall_memory
from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.repositories.squad_repository import SquadRepository
from app.services.adaptive_service import evaluate_after_bad_mood_task
from app.services.ai_service import AIService
from app.services.mercy_service import load_valid_dates
from app.services.points_service import PointsService
from app.services.shield_service import ShieldService
from app.services.streak_service import calc_streak, today_str, week_dates_of

logger = get_logger("challengePlanet.checkin")

_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro: object) -> None:
    task = asyncio.create_task(coro)  # type: ignore[arg-type]
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class CheckInService:
    def __init__(self, points: PointsService | None = None) -> None:
        self._repo = CheckInRepository()
        self._insight_repo = InsightRepository()
        self._challenge_repo = ChallengeRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._squad_repo = SquadRepository()
        self._points = points or PointsService()
        self._ai = AIService()
        self._shields = ShieldService()

    async def do_checkin(
        self,
        session: AsyncSession,
        challenge_id: int,
        user_id: str,
        mood: str,
        reflection: str,
        checkin_type: str = "full",
    ) -> dict[str, object]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        if checkin_type not in ("full", "mini"):
            raise ValueError("未知的打卡类型")

        today = today_str()
        existing = await self._repo.get_by_date(session, challenge_id, today)
        if existing is not None:
            streak = await self._current_streak(session, challenge_id)
            return {
                "checkin": existing, "ai_feedback": existing.ai_feedback,
                "points_earned": 0, "chest_points": 0, "streak": streak,
                "already_checked": True, "declaration": "", "shields": 0,
            }

        start_dt = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        day_number = min((datetime.now() - start_dt).days + 1, challenge.duration_days)
        if day_number < 1:
            raise ValueError("挑战还未开始")
        if checkin_type == "mini" and not reflection.strip():
            reflection = "微打卡：今天没放弃"

        memory_context = await self._recall_context(user_id, challenge.title)
        feedback, declaration = await asyncio.gather(
            self._safe_feedback(
                challenge.title, day_number, challenge.duration_days, mood, reflection, memory_context
            ),
            self._safe_declaration(challenge.title, day_number),
        )
        checkin = await self._repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "day_number": day_number,
            "date": today,
            "status": "completed",
            "checkin_type": checkin_type,
            "mood": mood,
            "reflection": reflection,
            "ai_feedback": feedback,
        })

        streak = await self._current_streak(session, challenge_id)
        base, chest = await self._points.award_checkin(
            session, user_id, challenge_id, streak, mini=checkin_type == "mini"
        )
        shields = await self._shields.award_milestone(session, challenge_id, streak)
        await self._maybe_award_squad_bonus(session, challenge_id, today)
        _fire_and_forget(self._save_memory(user_id, challenge.title, day_number, mood, reflection))
        if mood == "bad":
            _fire_and_forget(evaluate_after_bad_mood_task(challenge_id))
        if day_number % 7 == 0 or day_number == challenge.duration_days:
            _fire_and_forget(generate_weekly_report_task(challenge_id))

        return {
            "checkin": checkin, "ai_feedback": feedback,
            "points_earned": base, "chest_points": chest, "streak": streak,
            "already_checked": False, "declaration": declaration, "shields": shields,
        }

    async def update_today_reflection(
        self,
        session: AsyncSession,
        challenge_id: int,
        user_id: str,
        mood: str,
        reflection: str,
    ) -> CheckIn:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        today = today_str()
        checkin = await self._repo.get_by_date(session, challenge_id, today)
        if checkin is None:
            raise ValueError("今日还未打卡")
        memory_context = await self._recall_context(user_id, challenge.title)
        feedback = await self._safe_feedback(
            challenge.title, checkin.day_number, challenge.duration_days, mood, reflection, memory_context
        )
        updated = await self._repo.update(session, checkin, {
            "mood": mood, "reflection": reflection, "ai_feedback": feedback,
        })
        _fire_and_forget(
            self._save_memory(user_id, challenge.title, checkin.day_number, mood, reflection)
        )
        return updated

    async def _current_streak(self, session: AsyncSession, challenge_id: int) -> int:
        valid = await load_valid_dates(session, challenge_id)
        return calc_streak(valid, today_str())

    async def _recall_context(self, user_id: str, title: str) -> str:
        memories = await recall_memory(user_id, f"{title} 打卡 心情")
        return "；".join(memories[:3])

    async def _safe_feedback(
        self,
        title: str,
        day_number: int,
        total_days: int,
        mood: str,
        reflection: str,
        memory_context: str,
    ) -> str:
        try:
            return await self._ai.generate_daily_feedback(
                title, day_number, total_days, mood, reflection, memory_context
            )
        except Exception as e:
            logger.warning("daily feedback fallback: %s", e)
            return "坚持就是胜利！明天继续加油💪"

    async def _safe_declaration(self, title: str, day_number: int) -> str:
        try:
            streak = day_number
            return await self._ai.generate_declaration(title, day_number, streak)
        except Exception as e:
            logger.warning("declaration fallback: %s", e)
            return ""

    async def _maybe_award_squad_bonus(
        self, session: AsyncSession, challenge_id: int, today: str
    ) -> None:
        meta = await self._meta_repo.get(session, challenge_id)
        if meta is None or meta.squad_id is None:
            return
        members = await self._squad_repo.get_members(session, meta.squad_id)
        if not members:
            return
        for member in members:
            checked = await self._repo.user_has_checkin_on_date(session, member.user_id, today)
            if not checked:
                return
        await self._points.award_squad_bonus(
            session, [m.user_id for m in members], meta.squad_id, today
        )

    async def _save_memory(
        self, user_id: str, title: str, day_number: int, mood: str, reflection: str
    ) -> None:
        mood_text = mood or "未记录"
        reflection_text = reflection or "无"
        await add_memory(user_id, f"挑战「{title}」第{day_number}天打卡：心情{mood_text}，心得{reflection_text}")

    async def get_checkins(self, session: AsyncSession, challenge_id: int) -> list[CheckIn]:
        return await self._repo.get_by_challenge(session, challenge_id)

    async def get_insights(self, session: AsyncSession, challenge_id: int) -> list:
        return await self._insight_repo.get_by_challenge(session, challenge_id)

    async def get_weekly_report(
        self, session: AsyncSession, challenge_id: int
    ) -> dict[str, object]:
        insight = await self._insight_repo.get_latest_weekly(session, challenge_id)
        checkins = await self._repo.get_by_challenge(session, challenge_id)
        week_dates = set(week_dates_of())
        week_count = sum(1 for c in checkins if c.date in week_dates)
        return {
            "report": insight.content if insight else "",
            "generated_at": insight.created_at if insight else None,
            "week_checkins": week_count,
            "week_days": 7,
        }


async def generate_weekly_report_task(challenge_id: int) -> None:
    try:
        async with async_session() as session:
            challenge_repo = ChallengeRepository()
            challenge = await challenge_repo.get_by_id(session, challenge_id)
            if challenge is None:
                return
            checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
            checkin_data = [
                {"day_number": c.day_number, "mood": c.mood, "reflection": c.reflection}
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
