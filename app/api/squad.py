from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.squad import (
    NudgeRequest,
    SquadBoardResponse,
    SquadCreateRequest,
    SquadJoinRequest,
    SquadResponse,
)
from app.services.squad_service import SquadService

router = APIRouter(prefix="/squads", tags=["squads"])


def _bad_request(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.post("", response_model=SquadResponse)
async def create_squad(
    request: SquadCreateRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> SquadResponse:
    service = SquadService()
    squad = await service.create(session, request.name, user_id, request.nickname)
    await session.commit()
    return SquadResponse(
        id=squad.id,
        name=squad.name,
        invite_code=squad.invite_code,
        created_by=squad.created_by,
        member_count=1,
        created_at=squad.created_at,
    )


@router.post("/join", response_model=SquadResponse)
async def join_squad(
    request: SquadJoinRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> SquadResponse:
    service = SquadService()
    try:
        squad = await service.join(session, request.invite_code, user_id, request.nickname)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    members = await service.get_members(session, squad.id)
    return SquadResponse(
        id=squad.id,
        name=squad.name,
        invite_code=squad.invite_code,
        created_by=squad.created_by,
        member_count=len(members),
        created_at=squad.created_at,
    )


@router.get("/my", response_model=list[SquadResponse])
async def my_squads(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[SquadResponse]:
    service = SquadService()
    squads = await service.my_squads(session, user_id)
    results: list[SquadResponse] = []
    for squad in squads:
        members = await service.get_members(session, squad.id)
        results.append(SquadResponse(
            id=squad.id,
            name=squad.name,
            invite_code=squad.invite_code,
            created_by=squad.created_by,
            member_count=len(members),
            created_at=squad.created_at,
        ))
    return results


@router.get("/{squad_id}/board", response_model=SquadBoardResponse)
async def get_board(
    squad_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> SquadBoardResponse:
    service = SquadService()
    try:
        board = await service.get_board(session, squad_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    return SquadBoardResponse(**board)


@router.post("/{squad_id}/nudge")
async def nudge_member(
    squad_id: int,
    request: NudgeRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = SquadService()
    try:
        await service.nudge(session, squad_id, user_id, request.to_user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return {"ok": True}


@router.delete("/{squad_id}/leave")
async def leave_squad(
    squad_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = SquadService()
    try:
        await service.leave(session, squad_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return {"ok": True}
