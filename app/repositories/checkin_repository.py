from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn, AIInsight


class CheckInRepository:
    async def get_by_challenge(self, session: AsyncSession, challenge_id: int) -> list[CheckIn]:
        result = await session.execute(
            select(CheckIn).where(CheckIn.challenge_id == challenge_id).order_by(CheckIn.day_number)
        )
        return list(result.scalars().all())

    async def get_by_date(self, session: AsyncSession, challenge_id: int, date: str) -> CheckIn | None:
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date == date,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, session: AsyncSession, data: dict[str, object]) -> CheckIn:
        checkin = CheckIn(**data)
        session.add(checkin)
        await session.flush()
        return checkin

    async def update(self, session: AsyncSession, checkin: CheckIn, data: dict[str, object]) -> CheckIn:
        for key, value in data.items():
            setattr(checkin, key, value)
        await session.flush()
        return checkin

    async def count_by_challenge(self, session: AsyncSession, challenge_id: int) -> int:
        result = await session.execute(
            select(CheckIn).where(CheckIn.challenge_id == challenge_id)
        )
        return len(list(result.scalars().all()))

    async def user_has_checkin_on_date(self, session: AsyncSession, user_id: str, date: str) -> bool:
        result = await session.execute(
            select(CheckIn.id).where(
                CheckIn.user_id == user_id,
                CheckIn.date == date,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None


class InsightRepository:
    async def get_by_challenge(self, session: AsyncSession, challenge_id: int, limit: int = 10) -> list[AIInsight]:
        result = await session.execute(
            select(AIInsight)
            .where(AIInsight.challenge_id == challenge_id)
            .order_by(AIInsight.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, session: AsyncSession, data: dict[str, object]) -> AIInsight:
        insight = AIInsight(**data)
        session.add(insight)
        await session.flush()
        return insight

    async def get_latest_weekly(self, session: AsyncSession, challenge_id: int) -> AIInsight | None:
        result = await session.execute(
            select(AIInsight)
            .where(AIInsight.challenge_id == challenge_id, AIInsight.insight_type == "weekly")
            .order_by(AIInsight.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
