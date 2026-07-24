from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.challenge import WeeklyReportResponse
from app.schemas.checkin import (
    CheckInCreate,
    CheckInPatchRequest,
    CheckInResponse,
    CheckInResultResponse,
    DateActionRequest,
    DateActionResponse,
    InsightResponse,
    MercyStatusResponse,
    RepairResponse,
)
from app.services.checkin_service import CheckInService
from app.services.mercy_service import MercyService

router = APIRouter()


def _bad_request(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


@router.post("/{challenge_id}/checkin", response_model=CheckInResultResponse)
async def do_checkin(
    challenge_id: int,
    request: CheckInCreate,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CheckInResultResponse:
    service = CheckInService()
    try:
        result = await service.do_checkin(
            session, challenge_id, user_id,
            checkin_type=request.checkin_type,
            mood=request.mood,
            reflection=request.reflection,
            task_type=request.task_type,
            task_value=request.task_value,
            task_unit=request.task_unit,
            task_target=request.task_target,
            steps_done=request.steps_done,
        )
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return CheckInResultResponse(
        checkin=CheckInResponse.model_validate(result["checkin"]),
        ai_feedback=str(result["ai_feedback"]),
        points_earned=int(result["points_earned"]),
        chest_points=int(result["chest_points"]),
        streak=int(result["streak"]),
        already_checked=bool(result["already_checked"]),
        declaration=str(result.get("declaration", "")),
        shields=int(result.get("shields", 0)),
    )


@router.patch("/{challenge_id}/checkin/today", response_model=CheckInResponse)
async def patch_today_checkin(
    challenge_id: int,
    request: CheckInPatchRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CheckInResponse:
    service = CheckInService()
    try:
        checkin = await service.update_today_reflection(
            session, challenge_id, user_id, request.mood, request.reflection
        )
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return CheckInResponse.model_validate(checkin)


@router.post("/{challenge_id}/mend", response_model=DateActionResponse)
async def mend_checkin(
    challenge_id: int,
    request: DateActionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DateActionResponse:
    service = MercyService()
    try:
        result = await service.mend(session, challenge_id, user_id, request.date)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return DateActionResponse(**result)


@router.post("/{challenge_id}/freeze", response_model=DateActionResponse)
async def freeze_checkin(
    challenge_id: int,
    request: DateActionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DateActionResponse:
    service = MercyService()
    try:
        result = await service.freeze(session, challenge_id, user_id, request.date)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return DateActionResponse(**result)


@router.post("/{challenge_id}/repair", response_model=RepairResponse)
async def repair_streak(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> RepairResponse:
    service = MercyService()
    try:
        result = await service.repair(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return RepairResponse(**result)


@router.get("/{challenge_id}/mercy", response_model=MercyStatusResponse)
async def get_mercy_status(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> MercyStatusResponse:
    service = MercyService()
    try:
        result = await service.get_mercy_status(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return MercyStatusResponse(**result)


@router.get("/{challenge_id}/checkins", response_model=list[CheckInResponse])
async def get_checkins(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[CheckInResponse]:
    service = CheckInService()
    try:
        checkins = await service.get_checkins(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    return [CheckInResponse.model_validate(c) for c in checkins]


@router.get("/{challenge_id}/insights", response_model=list[InsightResponse])
async def get_insights(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[InsightResponse]:
    service = CheckInService()
    try:
        insights = await service.get_insights(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    return [InsightResponse.model_validate(i) for i in insights]


@router.get("/{challenge_id}/weekly-report", response_model=WeeklyReportResponse)
async def get_weekly_report(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> WeeklyReportResponse:
    service = CheckInService()
    try:
        result = await service.get_weekly_report(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    return WeeklyReportResponse(**result)
