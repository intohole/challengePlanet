from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.squad import Squad, SquadMember, SquadNudge


class SquadRepository:
    async def create_squad(self, session: AsyncSession, data: dict[str, object]) -> Squad:
        squad = Squad(**data)
        session.add(squad)
        await session.flush()
        return squad

    async def get_by_id(self, session: AsyncSession, squad_id: int) -> Squad | None:
        result = await session.execute(select(Squad).where(Squad.id == squad_id))
        return result.scalar_one_or_none()

    async def get_by_invite_code(self, session: AsyncSession, invite_code: str) -> Squad | None:
        result = await session.execute(select(Squad).where(Squad.invite_code == invite_code))
        return result.scalar_one_or_none()

    async def add_member(self, session: AsyncSession, data: dict[str, object]) -> SquadMember:
        member = SquadMember(**data)
        session.add(member)
        await session.flush()
        return member

    async def get_member(self, session: AsyncSession, squad_id: int, user_id: str) -> SquadMember | None:
        result = await session.execute(
            select(SquadMember).where(
                SquadMember.squad_id == squad_id,
                SquadMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_members(self, session: AsyncSession, squad_id: int) -> list[SquadMember]:
        result = await session.execute(
            select(SquadMember).where(SquadMember.squad_id == squad_id).order_by(SquadMember.joined_at)
        )
        return list(result.scalars().all())

    async def count_members(self, session: AsyncSession, squad_id: int) -> int:
        result = await session.execute(
            select(func.count(SquadMember.id)).where(SquadMember.squad_id == squad_id)
        )
        return int(result.scalar() or 0)

    async def remove_member(self, session: AsyncSession, member: SquadMember) -> None:
        await session.delete(member)
        await session.flush()

    async def get_squads_by_user(self, session: AsyncSession, user_id: str) -> list[Squad]:
        result = await session.execute(
            select(Squad)
            .join(SquadMember, SquadMember.squad_id == Squad.id)
            .where(SquadMember.user_id == user_id)
            .order_by(Squad.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_nudge(
        self, session: AsyncSession, squad_id: int, from_user: str, to_user: str, nudge_date: str
    ) -> SquadNudge | None:
        result = await session.execute(
            select(SquadNudge).where(
                SquadNudge.squad_id == squad_id,
                SquadNudge.from_user == from_user,
                SquadNudge.to_user == to_user,
                SquadNudge.nudge_date == nudge_date,
            )
        )
        return result.scalar_one_or_none()

    async def create_nudge(self, session: AsyncSession, data: dict[str, object]) -> SquadNudge:
        nudge = SquadNudge(**data)
        session.add(nudge)
        await session.flush()
        return nudge
