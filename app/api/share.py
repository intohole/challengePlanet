from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.checkin import ShareCardResponse
from app.services.challenge_service import ChallengeService

router = APIRouter()


@router.get("/{challenge_id}/share", response_model=ShareCardResponse)
async def get_share_card(challenge_id: int, session: AsyncSession = Depends(get_db)) -> ShareCardResponse:
    service = ChallengeService()
    data = await service.get_share_data(session, challenge_id)
    if data is None:
        return ShareCardResponse(
            challenge_id=challenge_id, title="", duration_days=0,
            current_day=0, total_checkins=0, streak=0, progress_pct=0,
            share_text="", share_token="",
        )
    return ShareCardResponse(**data)
