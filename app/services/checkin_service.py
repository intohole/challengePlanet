from __future__ import annotations

import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.schemas.checkin import CheckInCreate
from app.services.ai_service import AIService


class CheckInService:
    def __init__(self) -> None:
        self._repo = CheckInRepository()
        self._insight_repo = InsightRepository()
        self._challenge_repo = ChallengeRepository()
        self._ai = AIService()

    async def do_checkin(
        self, session: AsyncSession, challenge_id: int, request: CheckInCreate
    ) -> CheckIn:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None:
            raise ValueError("Challenge not found")

        today_str = datetime.now().strftime("%Y-%m-%d")
        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        day_number = min((datetime.now() - start_date).days + 1, challenge.duration_days)

        existing = await self._repo.get_by_date(session, challenge_id, today_str)
        if existing is not None:
            return existing

        feedback = ""
        try:
            feedback = await self._ai.generate_daily_feedback(
                challenge.title, day_number, challenge.duration_days,
                request.mood, request.reflection,
            )
        except Exception:
            feedback = "坚持就是胜利！明天继续加油💪"

        checkin = await self._repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": request.user_id,
            "day_number": day_number,
            "date": today_str,
            "status": "completed",
            "mood": request.mood,
            "reflection": request.reflection,
            "ai_feedback": feedback,
        })
        await session.commit()

        if day_number % 7 == 0 or day_number == challenge.duration_days:
            asyncio.create_task(self._generate_weekly_insight(session, challenge_id, challenge))

        return checkin

    async def _generate_weekly_insight(
        self, session: AsyncSession, challenge_id: int, challenge
    ) -> None:
        try:
            checkins = await self._repo.get_by_challenge(session, challenge_id)
            checkin_data = [
                {"day_number": c.day_number, "mood": c.mood, "reflection": c.reflection}
                for c in checkins
            ]
            insight_text = await self._ai.generate_insight(
                challenge.title, checkin_data, challenge.duration_days
            )
            await self._insight_repo.create(session, {
                "challenge_id": challenge_id,
                "user_id": challenge.user_id,
                "insight_type": "weekly",
                "content": insight_text,
            })
            await session.commit()
        except Exception as e:
            pass

    async def get_checkins(self, session: AsyncSession, challenge_id: int) -> list[CheckIn]:
        return await self._repo.get_by_challenge(session, challenge_id)

    async def get_insights(self, session: AsyncSession, challenge_id: int) -> list:
        return await self._insight_repo.get_by_challenge(session, challenge_id)
