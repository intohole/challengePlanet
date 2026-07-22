from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.challenge import PortalTodayResponse
from app.services.challenge_service import ChallengeService

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/today", response_model=PortalTodayResponse)
async def get_portal_today(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> PortalTodayResponse:
    service = ChallengeService()
    result = await service.get_portal_today(session, user_id)
    return PortalTodayResponse(**result)
