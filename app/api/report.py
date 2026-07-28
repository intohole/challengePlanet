from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.report import (
    CompletionRateResponse,
    HeatmapResponse,
    HourlyDistributionResponse,
    ReportOverviewResponse,
    TrendResponse,
)
from app.services.report_service import ReportService
from app.api._common import bad_request

router = APIRouter()


@router.get("/{challenge_id}/report/overview", response_model=ReportOverviewResponse)
async def get_overview(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ReportOverviewResponse:
    service = ReportService()
    try:
        result = await service.get_overview(session, challenge_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    return ReportOverviewResponse(**result)


@router.get("/{challenge_id}/report/hourly", response_model=HourlyDistributionResponse)
async def get_hourly_distribution(
    challenge_id: int,
    days: int = Query(7, ge=1, le=90),
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> HourlyDistributionResponse:
    service = ReportService()
    try:
        result = await service.get_hourly_distribution(session, challenge_id, user_id, days)
    except ValueError as e:
        raise bad_request(e)
    return HourlyDistributionResponse(**result)


@router.get("/{challenge_id}/report/trend", response_model=TrendResponse)
async def get_trend(
    challenge_id: int,
    days: int = Query(30, ge=1, le=365),
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> TrendResponse:
    service = ReportService()
    try:
        result = await service.get_trend(session, challenge_id, user_id, days)
    except ValueError as e:
        raise bad_request(e)
    return TrendResponse(**result)


@router.get("/{challenge_id}/report/heatmap", response_model=HeatmapResponse)
async def get_heatmap(
    challenge_id: int,
    year: int | None = Query(None),
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> HeatmapResponse:
    service = ReportService()
    try:
        result = await service.get_heatmap(session, challenge_id, user_id, year)
    except ValueError as e:
        raise bad_request(e)
    return HeatmapResponse(**result)


@router.get("/{challenge_id}/report/completion", response_model=CompletionRateResponse)
async def get_completion_rate(
    challenge_id: int,
    period: str = Query("week", regex="^(week|month)$"),
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CompletionRateResponse:
    service = ReportService()
    try:
        result = await service.get_completion_rate(session, challenge_id, user_id, period)
    except ValueError as e:
        raise bad_request(e)
    return CompletionRateResponse(**result)


@router.get("/{challenge_id}/today-detail")
async def get_today_detail(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = ReportService()
    try:
        result = await service.get_today_checkins_with_sub_goals(session, challenge_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    return result
