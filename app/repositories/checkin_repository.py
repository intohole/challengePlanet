from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn, AIInsight


class CheckInRepository:
    async def get_by_challenge(
        self, session: AsyncSession, challenge_id: int
    ) -> list[CheckIn]:
        result = await session.execute(
            select(CheckIn)
            .where(CheckIn.challenge_id == challenge_id)
            .order_by(CheckIn.timestamp.asc())
        )
        return list(result.scalars().all())

    async def get_by_date(
        self, session: AsyncSession, challenge_id: int, date: str
    ) -> CheckIn | None:
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date == date,
            ).order_by(CheckIn.timestamp.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_date(
        self, session: AsyncSession, challenge_id: int, date: str
    ) -> list[CheckIn]:
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date == date,
            ).order_by(CheckIn.timestamp.asc())
        )
        return list(result.scalars().all())

    async def sum_value_by_date(
        self, session: AsyncSession, challenge_id: int, date: str
    ) -> float:
        result = await session.execute(
            select(func.coalesce(func.sum(CheckIn.value), 0.0)).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date == date,
            )
        )
        return float(result.scalar_one() or 0.0)

    async def list_by_date_range(
        self, session: AsyncSession, challenge_id: int,
        start_date: str, end_date: str,
    ) -> list[CheckIn]:
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date >= start_date,
                CheckIn.date <= end_date,
            ).order_by(CheckIn.timestamp.asc())
        )
        return list(result.scalars().all())

    async def list_recent(
        self, session: AsyncSession, challenge_id: int, days: int = 7
    ) -> list[CheckIn]:
        cutoff = datetime.now() - timedelta(days=days)
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.timestamp >= cutoff,
            ).order_by(CheckIn.timestamp.asc())
        )
        return list(result.scalars().all())

    async def list_by_sub_goal(
        self, session: AsyncSession, sub_goal_id: int, date: str | None = None
    ) -> list[CheckIn]:
        stmt = select(CheckIn).where(CheckIn.sub_goal_id == sub_goal_id)
        if date:
            stmt = stmt.where(CheckIn.date == date)
        result = await session.execute(stmt.order_by(CheckIn.timestamp.asc()))
        return list(result.scalars().all())

    async def sum_value_by_sub_goal(
        self, session: AsyncSession, sub_goal_id: int, date: str
    ) -> float:
        result = await session.execute(
            select(func.coalesce(func.sum(CheckIn.value), 0.0)).where(
                CheckIn.sub_goal_id == sub_goal_id,
                CheckIn.date == date,
            )
        )
        return float(result.scalar_one() or 0.0)

    async def create(self, session: AsyncSession, data: dict[str, object]) -> CheckIn:
        checkin = CheckIn(**data)
        session.add(checkin)
        await session.flush()
        return checkin

    async def update(
        self, session: AsyncSession, checkin: CheckIn, data: dict[str, object]
    ) -> CheckIn:
        for key, value in data.items():
            setattr(checkin, key, value)
        await session.flush()
        return checkin

    async def delete(self, session: AsyncSession, checkin: CheckIn) -> None:
        await session.delete(checkin)
        await session.flush()

    async def count_by_challenge(self, session: AsyncSession, challenge_id: int) -> int:
        result = await session.execute(
            select(func.count(CheckIn.id)).where(CheckIn.challenge_id == challenge_id)
        )
        return int(result.scalar_one() or 0)

    async def count_active_days(self, session: AsyncSession, challenge_id: int) -> int:
        result = await session.execute(
            select(func.count(func.distinct(CheckIn.date))).where(
                CheckIn.challenge_id == challenge_id
            )
        )
        return int(result.scalar_one() or 0)

    async def user_has_checkin_on_date(
        self, session: AsyncSession, user_id: str, date: str
    ) -> bool:
        result = await session.execute(
            select(CheckIn.id).where(
                CheckIn.user_id == user_id,
                CheckIn.date == date,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_hourly_distribution(
        self, session: AsyncSession, challenge_id: int,
        start_date: str, end_date: str,
    ) -> list[dict[str, object]]:
        from sqlalchemy import extract
        result = await session.execute(
            select(
                extract("hour", CheckIn.timestamp).label("hour"),
                func.sum(CheckIn.value).label("total"),
                func.count(CheckIn.id).label("cnt"),
            ).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date >= start_date,
                CheckIn.date <= end_date,
            ).group_by("hour").order_by("hour")
        )
        return [
            {"hour": int(row.hour), "total_value": float(row.total or 0),
             "checkin_count": int(row.cnt or 0)}
            for row in result.fetchall()
        ]

    async def get_daily_totals(
        self, session: AsyncSession, challenge_id: int,
        start_date: str, end_date: str,
    ) -> list[dict[str, object]]:
        result = await session.execute(
            select(
                CheckIn.date,
                func.sum(CheckIn.value).label("total"),
                func.count(CheckIn.id).label("cnt"),
                func.max(CheckIn.target_value).label("target"),
            ).where(
                CheckIn.challenge_id == challenge_id,
                CheckIn.date >= start_date,
                CheckIn.date <= end_date,
            ).group_by(CheckIn.date).order_by(CheckIn.date.asc())
        )
        return [
            {"date": row.date, "value": float(row.total or 0),
             "checkin_count": int(row.cnt or 0), "target": float(row.target or 0)}
            for row in result.fetchall()
        ]


class InsightRepository:
    async def get_by_challenge(
        self, session: AsyncSession, challenge_id: int, limit: int = 10
    ) -> list[AIInsight]:
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

    async def get_latest_weekly(
        self, session: AsyncSession, challenge_id: int
    ) -> AIInsight | None:
        result = await session.execute(
            select(AIInsight)
            .where(AIInsight.challenge_id == challenge_id, AIInsight.insight_type == "weekly")
            .order_by(AIInsight.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
