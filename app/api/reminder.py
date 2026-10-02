from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.reminder import ReminderPref

router = APIRouter()

MIN_HOUR = 6
MAX_HOUR = 23


class ReminderPrefsResponse(BaseModel):
    remind_hour: int = 20
    enabled: bool = True


class ReminderPrefsUpdate(BaseModel):
    remind_hour: int = Field(default=20, ge=MIN_HOUR, le=MAX_HOUR)
    enabled: bool = True


@router.get("/reminder/prefs", response_model=ReminderPrefsResponse)
async def get_reminder_prefs(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ReminderPrefsResponse:
    result = await session.execute(
        select(ReminderPref).where(ReminderPref.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        return ReminderPrefsResponse()
    return ReminderPrefsResponse(remind_hour=pref.remind_hour, enabled=pref.enabled)


@router.put("/reminder/prefs", response_model=ReminderPrefsResponse)
async def update_reminder_prefs(
    payload: ReminderPrefsUpdate,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ReminderPrefsResponse:
    result = await session.execute(
        select(ReminderPref).where(ReminderPref.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if pref is None:
        pref = ReminderPref(user_id=user_id)
        session.add(pref)
    pref.remind_hour = payload.remind_hour
    pref.enabled = payload.enabled
    await session.commit()
    return ReminderPrefsResponse(remind_hour=pref.remind_hour, enabled=pref.enabled)
