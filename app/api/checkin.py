from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.checkin import CheckInCreate, CheckInResponse, InsightResponse
from app.services.checkin_service import CheckInService

router = APIRouter()


@router.post("/{challenge_id}/checkin", response_model=CheckInResponse)
async def do_checkin(
    challenge_id: int, request: CheckInCreate, session: AsyncSession = Depends(get_db)
) -> CheckInResponse:
    service = CheckInService()
    checkin = await service.do_checkin(session, challenge_id, request)
    return CheckInResponse.model_validate(checkin)


@router.get("/{challenge_id}/insights", response_model=list[InsightResponse])
async def get_insights(challenge_id: int, session: AsyncSession = Depends(get_db)) -> list[InsightResponse]:
    service = CheckInService()
    insights = await service.get_insights(session, challenge_id)
    return [InsightResponse.model_validate(i) for i in insights]


@router.get("/{challenge_id}/checkins", response_model=list[CheckInResponse])
async def get_checkins(challenge_id: int, session: AsyncSession = Depends(get_db)) -> list[CheckInResponse]:
    service = CheckInService()
    checkins = await service.get_checkins(session, challenge_id)
    return [CheckInResponse.model_validate(c) for c in checkins]
