from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import WeightRecord


class WeightRepository:
    async def get_by_challenge(
        self, session: AsyncSession, challenge_id: int,
    ) -> list[WeightRecord]:
        result = await session.execute(
            select(WeightRecord)
            .where(WeightRecord.challenge_id == challenge_id)
            .order_by(WeightRecord.date.asc(), WeightRecord.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_date(
        self, session: AsyncSession, challenge_id: int, date: str,
    ) -> WeightRecord | None:
        result = await session.execute(
            select(WeightRecord).where(
                WeightRecord.challenge_id == challenge_id,
                WeightRecord.date == date,
            ).order_by(WeightRecord.id.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, data: dict[str, object],
    ) -> WeightRecord:
        record = WeightRecord(**data)
        session.add(record)
        await session.flush()
        return record

    async def update(
        self, session: AsyncSession, record: WeightRecord, weight_kg: float,
    ) -> WeightRecord:
        record.weight_kg = weight_kg
        await session.flush()
        return record

    async def delete(self, session: AsyncSession, record_id: int) -> None:
        await session.execute(
            delete(WeightRecord).where(WeightRecord.id == record_id)
        )
        await session.flush()
