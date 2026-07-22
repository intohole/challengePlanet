from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CheckInCreate(BaseModel):
    mood: str = Field("", description="心情: good/normal/bad, 可空")
    reflection: str = Field("", description="心得体会, 可空")
    checkin_type: str = Field("full", description="打卡类型: full/mini")

    model_config = {"extra": "ignore"}


class CheckInPatchRequest(BaseModel):
    mood: str = Field("", description="心情")
    reflection: str = Field("", description="心得体会")


class CheckInResponse(BaseModel):
    id: int
    challenge_id: int
    user_id: str
    day_number: int
    date: str
    status: str = "completed"
    checkin_type: str = "full"
    mood: str = ""
    reflection: str = ""
    ai_feedback: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CheckInResultResponse(BaseModel):
    checkin: CheckInResponse
    ai_feedback: str = ""
    points_earned: int = 0
    chest_points: int = 0
    streak: int = 0
    already_checked: bool = False
    declaration: str = ""
    shields: int = 0


class DateActionRequest(BaseModel):
    date: str = Field(..., description="目标日期 YYYY-MM-DD")


class DateActionResponse(BaseModel):
    date: str
    cost: int = 0
    streak: int = 0


class RepairResponse(BaseModel):
    ok: bool = False
    message: str = ""
    streak: int = 0


class MercyStatusResponse(BaseModel):
    mend_left_this_month: int = 0
    freeze_left_this_week: int = 0
    repair_available: bool = False
    missed_dates: list[str] = Field(default_factory=list)
    streak: int = 0
    shields: int = 0
    shield_activated: bool = False


class InsightResponse(BaseModel):
    id: int
    challenge_id: int
    insight_type: str = "daily"
    content: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
