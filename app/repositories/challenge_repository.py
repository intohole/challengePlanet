from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.adaptive import AdaptiveSuggestion
from app.models.checkin import AIInsight, CheckIn
from app.models.points import ChallengeMeta, StreakAction
from app.models.sub_goal import SubGoal


class ChallengeRepository:
    async def get_by_user_id(self, session: AsyncSession, user_id: str) -> list[Challenge]:
        result = await session.execute(
            select(Challenge).where(Challenge.user_id == user_id).order_by(Challenge.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, session: AsyncSession, challenge_id: int) -> Challenge | None:
        result = await session.execute(select(Challenge).where(Challenge.id == challenge_id))
        return result.scalar_one_or_none()

    async def get_active_by_user_id(self, session: AsyncSession, user_id: str) -> list[Challenge]:
        result = await session.execute(
            select(Challenge).where(
                Challenge.user_id == user_id,
                Challenge.status == "active",
            ).order_by(Challenge.created_at.desc())
        )
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, data: dict[str, object]) -> Challenge:
        challenge = Challenge(**data)
        session.add(challenge)
        await session.flush()
        return challenge

    async def update(self, session: AsyncSession, challenge_id: int, data: dict[str, object]) -> None:
        await session.execute(
            update(Challenge).where(Challenge.id == challenge_id).values(**data)
        )
        await session.flush()

    async def delete_with_children(self, session: AsyncSession, challenge_id: int) -> None:
        for model in (CheckIn, SubGoal, AIInsight, StreakAction, ChallengeMeta, AdaptiveSuggestion):
            await session.execute(delete(model).where(model.challenge_id == challenge_id))
        await session.execute(delete(Challenge).where(Challenge.id == challenge_id))
        await session.flush()

    async def get_all_active(self, session: AsyncSession) -> list[Challenge]:
        result = await session.execute(
            select(Challenge).where(Challenge.status == "active")
        )
        return list(result.scalars().all())

    async def get_by_share_token(self, session: AsyncSession, token: str) -> Challenge | None:
        result = await session.execute(
            select(Challenge).where(Challenge.share_token == token)
        )
        return result.scalar_one_or_none()
