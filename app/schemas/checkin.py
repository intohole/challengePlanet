from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CheckInCreate(BaseModel):
    user_id: str = Field(..., description="用户ID")
    mood: str = Field("good", description="心情: good/normal/bad")
    reflection: str = Field("", description="心得体会")
    task_id: Optional[str] = Field(None, description="任务ID(忽略)")

    model_config = {"extra": "ignore"}


class CheckInResponse(BaseModel):
    id: int
    challenge_id: int
    user_id: str
    day_number: int
    date: str
    status: str = "completed"
    mood: str = "good"
    reflection: str = ""
    ai_feedback: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InsightResponse(BaseModel):
    id: int
    challenge_id: int
    insight_type: str = "daily"
    content: str = ""
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ShareCardResponse(BaseModel):
    challenge_id: int
    title: str
    duration_days: int
    current_day: int
    total_checkins: int
    streak: int
    progress_pct: float
    share_text: str
    share_token: str
