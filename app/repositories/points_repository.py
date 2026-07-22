from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.points import ChallengeMeta, PointsLedger, StreakAction


class PointsRepository:
    async def add_entry(self, session: AsyncSession, data: dict[str, object]) -> PointsLedger:
        entry = PointsLedger(**data)
        session.add(entry)
        await session.flush()
        return entry

    async def get_balance(self, session: AsyncSession, user_id: str) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(
                PointsLedger.user_id == user_id
            )
        )
        return int(result.scalar() or 0)

    async def get_week_points(self, session: AsyncSession, user_id: str, week_key: str) -> int:
        result = await session.execute(
            select(func.coalesce(func.sum(PointsLedger.delta), 0)).where(
                PointsLedger.user_id == user_id,
                PointsLedger.week_key == week_key,
            )
        )
        return int(result.scalar() or 0)

    async def get_week_leaderboard(
        self, session: AsyncSession, week_key: str, user_ids: list[str] | None
    ) -> list[tuple[str, int]]:
        stmt = select(
            PointsLedger.user_id,
            func.coalesce(func.sum(PointsLedger.delta), 0).label("points"),
        ).where(PointsLedger.week_key == week_key)
        if user_ids is not None:
            stmt = stmt.where(PointsLedger.user_id.in_(user_ids))
        stmt = stmt.group_by(PointsLedger.user_id).order_by(func.sum(PointsLedger.delta).desc())
        result = await session.execute(stmt)
        return [(str(row[0]), int(row[1])) for row in result.fetchall()]

    async def get_ledger(
        self, session: AsyncSession, user_id: str, limit: int = 20
    ) -> list[PointsLedger]:
        result = await session.execute(
            select(PointsLedger)
            .where(PointsLedger.user_id == user_id)
            .order_by(PointsLedger.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class StreakActionRepository:
    async def create(self, session: AsyncSession, data: dict[str, object]) -> StreakAction:
        action = StreakAction(**data)
        session.add(action)
        await session.flush()
        return action

    async def get_by_challenge(self, session: AsyncSession, challenge_id: int) -> list[StreakAction]:
        result = await session.execute(
            select(StreakAction).where(StreakAction.challenge_id == challenge_id)
        )
        return list(result.scalars().all())

    async def count_user_actions_in_month(
        self, session: AsyncSession, user_id: str, action: str, month_prefix: str
    ) -> int:
        result = await session.execute(
            select(func.count(StreakAction.id)).where(
                StreakAction.user_id == user_id,
                StreakAction.action == action,
                StreakAction.action_date.like(f"{month_prefix}%"),
            )
        )
        return int(result.scalar() or 0)

    async def count_challenge_actions_in_month(
        self, session: AsyncSession, challenge_id: int, action: str, month_prefix: str
    ) -> int:
        result = await session.execute(
            select(func.count(StreakAction.id)).where(
                StreakAction.challenge_id == challenge_id,
                StreakAction.action == action,
                StreakAction.action_date.like(f"{month_prefix}%"),
            )
        )
        return int(result.scalar() or 0)

    async def count_user_actions_in_dates(
        self, session: AsyncSession, user_id: str, action: str, dates: list[str]
    ) -> int:
        if not dates:
            return 0
        result = await session.execute(
            select(func.count(StreakAction.id)).where(
                StreakAction.user_id == user_id,
                StreakAction.action == action,
                StreakAction.action_date.in_(dates),
            )
        )
        return int(result.scalar() or 0)

    async def get_by_date(
        self, session: AsyncSession, challenge_id: int, action: str, action_date: str
    ) -> StreakAction | None:
        result = await session.execute(
            select(StreakAction).where(
                StreakAction.challenge_id == challenge_id,
                StreakAction.action == action,
                StreakAction.action_date == action_date,
            )
        )
        return result.scalar_one_or_none()


class ChallengeMetaRepository:
    async def get(self, session: AsyncSession, challenge_id: int) -> ChallengeMeta | None:
        result = await session.execute(
            select(ChallengeMeta).where(ChallengeMeta.challenge_id == challenge_id)
        )
        return result.scalar_one_or_none()

    async def upsert(self, session: AsyncSession, challenge_id: int, data: dict[str, object]) -> ChallengeMeta:
        meta = await self.get(session, challenge_id)
        if meta is None:
            meta = ChallengeMeta(challenge_id=challenge_id, **data)
            session.add(meta)
        else:
            for key, value in data.items():
                setattr(meta, key, value)
        await session.flush()
        return meta
