from __future__ import annotations

import math
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.points import PointsLedger
from app.repositories.points_repository import PointsRepository
from app.services.streak_service import today_str, week_key_of

CHECKIN_BASE_POINTS = 5
MINI_CHECKIN_POINTS = 3
MIN_FULL_POINTS = 2
STREAK_BONUS_CAP = 7
CHEST_PROBABILITY = 0.18
CHEST_PROBABILITY_HIGH = 0.25
CHEST_MIN = 5
CHEST_MAX = 25
DAILY_EARN_CAP_PER_CHALLENGE = 30
_EARN_REASONS = ("checkin", "chest", "mini_checkin")


class PointsService:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._repo = PointsRepository()
        self._rng = rng or random.Random()

    async def _earned_today(self, session: AsyncSession, user_id: str, challenge_id: int) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(
                PointsLedger.user_id == user_id,
                PointsLedger.ref_id == str(challenge_id),
                PointsLedger.delta > 0,
                PointsLedger.reason.in_(_EARN_REASONS),
                func.date(PointsLedger.created_at) == today_str(),
            )
        )
        return int(result.scalar() or 0)

    async def award_checkin(
        self, session: AsyncSession, user_id: str, challenge_id: int, streak_after: int,
        mini: bool = False, completion_pct: float = 100.0,
    ) -> tuple[int, int]:
        earned_today = await self._earned_today(session, user_id, challenge_id)
        if earned_today >= DAILY_EARN_CAP_PER_CHALLENGE:
            return 0, 0
        if mini:
            await self._repo.add_entry(session, {
                "user_id": user_id,
                "delta": MINI_CHECKIN_POINTS,
                "reason": "mini_checkin",
                "ref_id": str(challenge_id),
                "week_key": week_key_of(),
            })
            return MINI_CHECKIN_POINTS, 0
        base = max(MIN_FULL_POINTS, math.floor(CHECKIN_BASE_POINTS * completion_pct / 100))
        base += min(streak_after, STREAK_BONUS_CAP)
        base = min(base, DAILY_EARN_CAP_PER_CHALLENGE - earned_today)
        await self._repo.add_entry(session, {
            "user_id": user_id,
            "delta": base,
            "reason": "checkin",
            "ref_id": str(challenge_id),
            "week_key": week_key_of(),
        })
        chest = 0
        chest_room = DAILY_EARN_CAP_PER_CHALLENGE - earned_today - base
        if completion_pct >= 50 and chest_room > 0:
            prob = CHEST_PROBABILITY_HIGH if completion_pct >= 80 else CHEST_PROBABILITY
            if self._rng.random() < prob:
                chest = min(self._rng.randint(CHEST_MIN, CHEST_MAX), chest_room)
                await self._repo.add_entry(session, {
                    "user_id": user_id,
                    "delta": chest,
                    "reason": "chest",
                    "ref_id": str(challenge_id),
                    "week_key": week_key_of(),
                })
        return base, chest

    async def spend(
        self, session: AsyncSession, user_id: str, amount: int, reason: str, ref_id: str = ""
    ) -> bool:
        balance = await self._repo.get_balance(session, user_id)
        if balance < amount:
            return False
        await self._repo.add_entry(session, {
            "user_id": user_id,
            "delta": -amount,
            "reason": reason,
            "ref_id": ref_id,
            "week_key": week_key_of(),
        })
        return True

    async def get_balance(self, session: AsyncSession, user_id: str) -> int:
        return await self._repo.get_balance(session, user_id)

    async def get_week_points(self, session: AsyncSession, user_id: str, week_key: str) -> int:
        return await self._repo.get_week_points(session, user_id, week_key)

