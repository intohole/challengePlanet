from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from nexus.permissions import require_admin_id
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.recall import RecallTrackRequest
from app.services.recall_service import build_funnel, track_event

router = APIRouter()


@router.post("/recall/track")
async def track_recall(
    body: RecallTrackRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await track_event(
        session, user_id, int(body.challenge_id or 0),
        str(body.channel or ""), str(body.stage or ""),
        notif_id=str(body.notif_id or ""), detail=str(body.detail or ""),
    )


@router.get("/recall/funnel")
async def recall_funnel(
    days: int = 7,
    admin_id: str = Depends(require_admin_id()),
    session: AsyncSession = Depends(get_db),
) -> dict:
    return await build_funnel(session, days=days, user_id=None)
