from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sub_goal import SubGoal


class SubGoalRepository:
    async def get_by_challenge(
        self, session: AsyncSession, challenge_id: int
    ) -> list[SubGoal]:
        result = await session.execute(
            select(SubGoal)
            .where(SubGoal.challenge_id == challenge_id, SubGoal.is_active == True)  # noqa: E712
            .order_by(SubGoal.order.asc(), SubGoal.id.asc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self, session: AsyncSession, sub_goal_id: int
    ) -> SubGoal | None:
        result = await session.execute(
            select(SubGoal).where(SubGoal.id == sub_goal_id)
        )
        return result.scalar_one_or_none()

    async def get_by_time_window(
        self, session: AsyncSession, challenge_id: int, hhmm: str
    ) -> SubGoal | None:
        result = await session.execute(
            select(SubGoal).where(
                SubGoal.challenge_id == challenge_id,
                SubGoal.is_active == True,  # noqa: E712
                SubGoal.time_window_start <= hhmm,
                SubGoal.time_window_end > hhmm,
            ).order_by(SubGoal.order.asc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def create(
        self, session: AsyncSession, data: dict[str, object]
    ) -> SubGoal:
        sub_goal = SubGoal(**data)
        session.add(sub_goal)
        await session.flush()
        return sub_goal

    async def batch_create(
        self, session: AsyncSession, items: list[dict[str, object]]
    ) -> list[SubGoal]:
        result: list[SubGoal] = []
        for item in items:
            sub_goal = SubGoal(**item)
            session.add(sub_goal)
            result.append(sub_goal)
        await session.flush()
        return result

    async def update(
        self, session: AsyncSession, sub_goal: SubGoal, data: dict[str, object]
    ) -> SubGoal:
        for key, value in data.items():
            setattr(sub_goal, key, value)
        await session.flush()
        return sub_goal

    async def deactivate_by_challenge(
        self, session: AsyncSession, challenge_id: int
    ) -> None:
        result = await session.execute(
            select(SubGoal).where(
                SubGoal.challenge_id == challenge_id,
                SubGoal.is_active == True,  # noqa: E712
            )
        )
        for sub_goal in result.scalars().all():
            sub_goal.is_active = False
        await session.flush()

    async def delete(self, session: AsyncSession, sub_goal: SubGoal) -> None:
        await session.delete(sub_goal)
        await session.flush()

    async def count_by_challenge(
        self, session: AsyncSession, challenge_id: int
    ) -> int:
        result = await session.execute(
            select(func.count(SubGoal.id)).where(
                SubGoal.challenge_id == challenge_id,
                SubGoal.is_active == True,  # noqa: E712
            )
        )
        return int(result.scalar_one() or 0)
