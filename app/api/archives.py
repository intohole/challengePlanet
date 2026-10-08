from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.archive_service import list_archives, user_summary

router = APIRouter()


class JourneyArchiveItem(BaseModel):
    id: int
    title: str
    category: str
    icon: str
    color: str
    unit: str
    start_date: str
    end_date: str
    total_days: int
    completed_days: int
    total_checkins: int
    streak_best: int
    avoided_total: int
    baseline: float
    final_cap: float
    graduation_state: str
    milestones: list[str]
    archived_at: str


@router.get("/archives", response_model=list[JourneyArchiveItem])
async def get_archives(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[JourneyArchiveItem]:
    rows = await list_archives(session, user_id)
    return [JourneyArchiveItem(**row) for row in rows]


@router.get("/archives/summary")
async def get_archives_summary(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    return await user_summary(session, user_id)
