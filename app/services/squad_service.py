from __future__ import annotations

import secrets

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.squad import Squad, SquadMember
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import PointsRepository
from app.repositories.squad_repository import SquadRepository
from app.services.streak_service import today_str, week_key_of

SQUAD_MAX_MEMBERS = 6
_INVITE_CODE_LENGTH = 8


class SquadService:
    def __init__(self) -> None:
        self._repo = SquadRepository()
        self._checkin_repo = CheckInRepository()
        self._points_repo = PointsRepository()

    async def create(
        self, session: AsyncSession, name: str, user_id: str, nickname: str
    ) -> Squad:
        invite_code = secrets.token_hex(_INVITE_CODE_LENGTH // 2)
        while await self._repo.get_by_invite_code(session, invite_code) is not None:
            invite_code = secrets.token_hex(_INVITE_CODE_LENGTH // 2)
        squad = await self._repo.create_squad(session, {
            "name": name,
            "invite_code": invite_code,
            "created_by": user_id,
        })
        await self._repo.add_member(session, {
            "squad_id": squad.id,
            "user_id": user_id,
            "nickname": nickname,
        })
        return squad

    async def join(
        self, session: AsyncSession, invite_code: str, user_id: str, nickname: str
    ) -> Squad:
        squad = await self._repo.get_by_invite_code(session, invite_code)
        if squad is None:
            raise ValueError("邀请码无效")
        existing = await self._repo.get_member(session, squad.id, user_id)
        if existing is not None:
            return squad
        count = await self._repo.count_members(session, squad.id)
        if count >= SQUAD_MAX_MEMBERS:
            raise ValueError("小队已满员（最多6人）")
        await self._repo.add_member(session, {
            "squad_id": squad.id,
            "user_id": user_id,
            "nickname": nickname,
        })
        return squad

    async def leave(self, session: AsyncSession, squad_id: int, user_id: str) -> None:
        member = await self._repo.get_member(session, squad_id, user_id)
        if member is None:
            raise ValueError("你不在该小队中")
        await self._repo.remove_member(session, member)

    async def my_squads(self, session: AsyncSession, user_id: str) -> list[Squad]:
        return await self._repo.get_squads_by_user(session, user_id)

    async def get_members(self, session: AsyncSession, squad_id: int) -> list[SquadMember]:
        return await self._repo.get_members(session, squad_id)

    async def get_member(self, session: AsyncSession, squad_id: int, user_id: str) -> SquadMember | None:
        return await self._repo.get_member(session, squad_id, user_id)

    async def get_board(
        self, session: AsyncSession, squad_id: int, user_id: str
    ) -> dict[str, object]:
        squad = await self._repo.get_by_id(session, squad_id)
        if squad is None:
            raise ValueError("小队不存在")
        member = await self._repo.get_member(session, squad_id, user_id)
        if member is None:
            raise ValueError("你不在该小队中")
        members = await self._repo.get_members(session, squad_id)
        today = today_str()
        week_key = week_key_of()
        items: list[dict[str, object]] = []
        for m in members:
            checked = await self._checkin_repo.user_has_checkin_on_date(session, m.user_id, today)
            week_points = await self._points_repo.get_week_points(session, m.user_id, week_key)
            items.append({
                "user_id": m.user_id,
                "nickname": m.nickname,
                "checked_today": checked,
                "week_points": week_points,
            })
        return {
            "squad_id": squad.id,
            "name": squad.name,
            "invite_code": squad.invite_code,
            "week_key": week_key,
            "members": items,
        }

    async def nudge(
        self, session: AsyncSession, squad_id: int, from_user: str, to_user: str
    ) -> None:
        if from_user == to_user:
            raise ValueError("不能戳自己")
        from_member = await self._repo.get_member(session, squad_id, from_user)
        to_member = await self._repo.get_member(session, squad_id, to_user)
        if from_member is None or to_member is None:
            raise ValueError("双方必须都在小队中")
        today = today_str()
        existing = await self._repo.get_nudge(session, squad_id, from_user, to_user, today)
        if existing is not None:
            raise ValueError("今天已经戳过TA了")
        await self._repo.create_nudge(session, {
            "squad_id": squad_id,
            "from_user": from_user,
            "to_user": to_user,
            "nudge_date": today,
        })
