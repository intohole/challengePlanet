from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HourlyDistributionItem(BaseModel):
    hour: int = Field(..., description="小时 0-23")
    total_value: float = 0.0
    checkin_count: int = 0
    target_value: float = 0.0
    exceed_pct: float = 0.0


class HourlyDistributionResponse(BaseModel):
    challenge_id: int
    date_range: str = "7d"
    direction: str = "increase"
    unit: str = "次"
    items: list[HourlyDistributionItem] = Field(default_factory=list)
    peak_hour: int = -1
    peak_value: float = 0.0
    insight: str = ""


class TrendPoint(BaseModel):
    date: str
    value: float = 0.0
    target: float = 0.0
    baseline: float = 0.0
    checkin_count: int = 0


class TrendResponse(BaseModel):
    challenge_id: int
    granularity: str = "daily"
    direction: str = "increase"
    unit: str = "次"
    points: list[TrendPoint] = Field(default_factory=list)
    avg_value: float = 0.0
    trend_direction: str = "stable"
    insight: str = ""


class HeatmapCell(BaseModel):
    date: str
    value: float = 0.0
    target: float = 0.0
    checkin_count: int = 0
    level: int = 0


class HeatmapResponse(BaseModel):
    challenge_id: int
    year: int
    direction: str = "increase"
    unit: str = "次"
    cells: list[HeatmapCell] = Field(default_factory=list)
    total_days: int = 0
    active_days: int = 0
    on_track_days: int = 0


class CompletionRateResponse(BaseModel):
    challenge_id: int
    period: str = "week"
    direction: str = "increase"
    unit: str = "次"
    on_track_days: int = 0
    total_days: int = 0
    completion_rate: float = 0.0
    soft_exceed_days: int = 0
    hard_exceed_days: int = 0
    insight: str = ""


class ReportOverviewResponse(BaseModel):
    challenge_id: int
    challenge_title: str = ""
    direction: str = "increase"
    unit: str = "次"
    today_total: float = 0.0
    today_target: float = 0.0
    dynamic_baseline: float = 0.0
    streak: int = 0
    total_checkins: int = 0
    active_days: int = 0
    last_7d_avg: float = 0.0
    last_7d_total: float = 0.0
    last_30d_avg: float = 0.0
    best_hour: int = -1
    worst_hour: int = -1
    peak_hour: int = -1
    generated_at: Optional[datetime] = None
    insight: str = ""
