from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PointsSummaryResponse(BaseModel):
    total: int = 0
    week_points: int = 0
    week_key: str = ""


class LeaderboardEntry(BaseModel):
    user_id: str
    nickname: str = ""
    points: int = 0


class LeaderboardResponse(BaseModel):
    week_key: str
    scope: str = "global"
    entries: list[LeaderboardEntry] = Field(default_factory=list)
