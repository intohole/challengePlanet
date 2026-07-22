from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChallengeCreate(BaseModel):
    user_id: str = Field(..., description="用户ID")
    title: str = Field(..., description="挑战标题")
    description: str = Field("", description="挑战描述")
    category: str = Field("build", description="分类: quit/build/learn/exercise/other")
    duration_days: int = Field(30, description="挑战天数")


class ChallengeResponse(BaseModel):
    id: int
    user_id: str
    title: str
    description: str = ""
    category: str = "build"
    duration_days: int = 30
    total_days: int = 0
    completed_days: int = 0
    streak: int = 0
    start_date: str = ""
    end_date: str = ""
    status: str = "active"
    ai_plan: list[dict[str, object]] = Field(default_factory=list)
    color: str = "#6366f1"
    icon: str = "🎯"
    is_shared: bool = False
    share_token: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TodayTaskResponse(BaseModel):
    challenge_id: int
    day_number: int
    date: str
    task: dict[str, object] = Field(default_factory=dict)
    task_title: str = ""
    task_description: str = ""
    task_tip: str = ""
    checked_in: bool = False
    checkin_data: Optional[dict[str, object]] = None
    streak: int = 0
    total_checkins: int = 0
    progress_pct: float = 0.0


class ChallengeStats(BaseModel):
    total_challenges: int = 0
    active_challenges: int = 0
    completed_challenges: int = 0
    total_checkins: int = 0
    best_streak: int = 0
    current_streak: int = 0
