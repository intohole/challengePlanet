from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubGoalCreate(BaseModel):
    title: str = Field(..., description="子目标标题")
    time_window_start: str = Field("", description="时段开始 HH:MM")
    time_window_end: str = Field("", description="时段结束 HH:MM")
    target_value: float = Field(0.0, description="时段目标值")
    goal_type: str = Field("soft", description="soft | hard")
    weight: float = Field(1.0, description="聚合权重")
    order: int = Field(0, description="排序")


class SubGoalBatchCreate(BaseModel):
    sub_goals: list[SubGoalCreate] = Field(default_factory=list)


class SubGoalResponse(BaseModel):
    id: int
    challenge_id: int
    user_id: str
    title: str
    time_window_start: str = ""
    time_window_end: str = ""
    target_value: float = 0.0
    goal_type: str = "soft"
    weight: float = 1.0
    order: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None

    today_value: float = 0.0
    today_checkin_count: int = 0
    progress_pct: float = 0.0

    model_config = {"from_attributes": True}


class SubGoalAutoDecomposeRequest(BaseModel):
    slot_hours: int = Field(1, description="每个时段多少小时(1/2/4/6/12)")
    target_per_slot: float = Field(0.0, description="每个时段目标(0=均分日目标)")
    goal_type: str = Field("soft", description="soft | hard")


class SubGoalAutoDecomposeResponse(BaseModel):
    sub_goals: list[SubGoalResponse] = Field(default_factory=list)
    message: str = ""
