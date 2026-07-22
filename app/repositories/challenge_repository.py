from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge


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

    async def get_by_share_token(self, session: AsyncSession, token: str) -> Challenge | None:
        result = await session.execute(
            select(Challenge).where(Challenge.share_token == token)
        )
        return result.scalar_one_or_none()
