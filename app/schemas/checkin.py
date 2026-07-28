from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CheckInCreate(BaseModel):
    value: float = Field(1.0, description="本次打卡值(如本次抽1根)")
    mood: str = Field("", description="心情: good/normal/bad")
    reflection: str = Field("", description="心得")
    sub_goal_id: Optional[int] = Field(None, description="所属时段子目标ID")
    context_tag: str = Field("", description="情境标签: home/work/social/stress")
    timestamp: Optional[datetime] = Field(None, description="打卡时间(默认当前时间)")

    model_config = {"extra": "ignore"}


class CheckInPatchRequest(BaseModel):
    mood: str = Field("", description="心情")
    reflection: str = Field("", description="心得体会")


class CheckInResponse(BaseModel):
    id: int
    challenge_id: int
    user_id: str
    sub_goal_id: Optional[int] = None
    day_number: int = 0
    timestamp: datetime
    date: str
    value: float = 0.0
    unit: str = "次"
    target_value: float = 0.0
    goal_type: str = "hard"
    direction: str = "increase"
    completion_pct: float = 100.0
    mood: str = ""
    reflection: str = ""
    ai_feedback: str = ""
    context_tag: str = ""
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

    today_total: float = 0.0
    today_target: float = 0.0
    dynamic_baseline: float = 0.0
    remaining: float = 0.0
    is_soft_exceeded: bool = False
    soft_exceeded_amount: float = 0.0


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
