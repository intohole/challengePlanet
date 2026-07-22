from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.challenge import ShareDataResponse
from app.services.challenge_service import ChallengeService

router = APIRouter()


@router.get("/share/{share_token}", response_model=ShareDataResponse)
async def get_shared_challenge(
    share_token: str, session: AsyncSession = Depends(get_db)
) -> ShareDataResponse:
    service = ChallengeService()
    data = await service.get_share_data_by_token(session, share_token)
    if data is None:
        raise HTTPException(status_code=404, detail="分享不存在")
    await session.commit()
    return ShareDataResponse(**data)
