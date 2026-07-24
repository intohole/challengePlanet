from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CheckInCreate(BaseModel):
    mood: str = Field("", description="心情: good/normal/bad, 可空")
    reflection: str = Field("", description="心得体会, 可空")
    checkin_type: str = Field("full", description="打卡类型: full/mini")
    task_type: str = Field("binary", description="任务类型: binary/counter/timer/choice/step/text")
    task_value: float = Field(0, description="实际完成值(计数/计时等)")
    task_unit: str = Field("", description="单位: 个/分钟/页/次等")
    task_target: float = Field(0, description="目标值")
    steps_done: list[str] = Field(default_factory=list, description="多步骤已完成步骤")

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
    task_type: str = "binary"
    task_data: dict[str, object] = Field(default_factory=dict)
    completion_pct: float = 100.0
    created_at: Optional[datetime] = None

    @field_validator("task_data", mode="before")
    @classmethod
    def parse_task_data(cls, v: object) -> dict[str, object]:
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, dict) else {}
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(v, dict):
            return v
        return {}

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
