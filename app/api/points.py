from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.points import (
    LeaderboardEntry,
    LeaderboardResponse,
    LedgerEntryResponse,
    PointsSummaryResponse,
)
from app.services.points_service import PointsService
from app.services.squad_service import SquadService
from app.services.streak_service import week_key_of

router = APIRouter()


@router.get("/points/summary", response_model=PointsSummaryResponse)
async def get_points_summary(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> PointsSummaryResponse:
    service = PointsService()
    week_key = week_key_of()
    total = await service.get_balance(session, user_id)
    week_points = await service.get_week_points(session, user_id, week_key)
    return PointsSummaryResponse(total=total, week_points=week_points, week_key=week_key)


@router.get("/points/ledger", response_model=list[LedgerEntryResponse])
async def get_points_ledger(
    limit: int = 20,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[LedgerEntryResponse]:
    service = PointsService()
    entries = await service.get_ledger(session, user_id, min(max(limit, 1), 100))
    return [LedgerEntryResponse.model_validate(e) for e in entries]


@router.get("/leaderboard/weekly", response_model=LeaderboardResponse)
async def get_weekly_leaderboard(
    scope: str = "global",
    squad_id: int | None = None,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> LeaderboardResponse:
    week_key = week_key_of()
    service = PointsService()
    if scope == "squad":
        if squad_id is None:
            raise HTTPException(status_code=400, detail="squad 榜单必须提供 squad_id")
        squad_service = SquadService()
        member = await squad_service.get_member(session, squad_id, user_id)
        if member is None:
            raise HTTPException(status_code=403, detail="你不在该小队中")
        members = await squad_service.get_members(session, squad_id)
        user_ids = [m.user_id for m in members]
        nicknames = {m.user_id: m.nickname for m in members}
        rows = await service.get_leaderboard(session, week_key, user_ids)
        entries = [
            LeaderboardEntry(
                user_id=str(row["user_id"]),
                nickname=nicknames.get(str(row["user_id"]), ""),
                points=int(row["points"]),
            )
            for row in rows
        ]
        return LeaderboardResponse(week_key=week_key, scope=scope, entries=entries)
    rows = await service.get_leaderboard(session, week_key, None)
    entries = [
        LeaderboardEntry(user_id=str(row["user_id"]), points=int(row["points"]))
        for row in rows
    ]
    return LeaderboardResponse(week_key=week_key, scope="global", entries=entries)
