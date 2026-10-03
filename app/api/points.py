from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.points import PointsSummaryResponse
from app.services.points_service import PointsService
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
