from __future__ import annotations

import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.points import PointsLedger
from app.repositories.points_repository import PointsRepository
from app.services.streak_service import week_key_of

CHECKIN_BASE_POINTS = 5
MINI_CHECKIN_POINTS = 3
STREAK_BONUS_CAP = 7
CHEST_PROBABILITY = 0.18
CHEST_MIN = 5
CHEST_MAX = 25
SQUAD_BONUS_POINTS = 5


class PointsService:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._repo = PointsRepository()
        self._rng = rng or random.Random()

    async def award_checkin(
        self, session: AsyncSession, user_id: str, challenge_id: int, streak_after: int, mini: bool = False
    ) -> tuple[int, int]:
        if mini:
            await self._repo.add_entry(session, {
                "user_id": user_id,
                "delta": MINI_CHECKIN_POINTS,
                "reason": "mini_checkin",
                "ref_id": str(challenge_id),
                "week_key": week_key_of(),
            })
            return MINI_CHECKIN_POINTS, 0
        base = CHECKIN_BASE_POINTS + min(streak_after, STREAK_BONUS_CAP)
        await self._repo.add_entry(session, {
            "user_id": user_id,
            "delta": base,
            "reason": "checkin",
            "ref_id": str(challenge_id),
            "week_key": week_key_of(),
        })
        chest = 0
        if self._rng.random() < CHEST_PROBABILITY:
            chest = self._rng.randint(CHEST_MIN, CHEST_MAX)
            await self._repo.add_entry(session, {
                "user_id": user_id,
                "delta": chest,
                "reason": "chest",
                "ref_id": str(challenge_id),
                "week_key": week_key_of(),
            })
        return base, chest

    async def award_squad_bonus(
        self, session: AsyncSession, user_ids: list[str], squad_id: int, date_str: str
    ) -> None:
        for uid in user_ids:
            await self._repo.add_entry(session, {
                "user_id": uid,
                "delta": SQUAD_BONUS_POINTS,
                "reason": "squad_bonus",
                "ref_id": f"squad:{squad_id}:{date_str}",
                "week_key": week_key_of(),
            })

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

    async def get_leaderboard(
        self, session: AsyncSession, week_key: str, scope_user_ids: list[str] | None = None
    ) -> list[dict[str, object]]:
        rows = await self._repo.get_week_leaderboard(session, week_key, scope_user_ids)
        return [{"user_id": uid, "points": pts} for uid, pts in rows]

    async def get_ledger(
        self, session: AsyncSession, user_id: str, limit: int = 20
    ) -> list[PointsLedger]:
        return await self._repo.get_ledger(session, user_id, limit)
