from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class BenchmarkData(BaseModel):
    avg_streak: int = 0
    avg_completion_rate: int = 0
    drop_off_day: int = 0
    scene_tip: str = ""


class NextMilestone(BaseModel):
    day: int = 0
    tip: str = ""
    days_to_go: int = 0


class GuidanceResponse(BaseModel):
    phase: str = "adaptation"
    phase_name: str = "适应期"
    phase_range: str = "第1-7天"
    phase_desc: str = ""
    phase_tip: str = ""
    phase_color: str = "#FF8A65"
    phase_icon: str = "🌱"
    completed_days: int = 0
    total_days: int = 0
    streak: int = 0
    completion_rate: int = 0
    benchmark: BenchmarkData = Field(default_factory=BenchmarkData)
    percentile: int = 0
    next_milestone: NextMilestone = Field(default_factory=NextMilestone)
    milestone_tip: str = ""
    is_at_risk: bool = False
    encouragement: str = ""


class SharedConfigResponse(BaseModel):
    title: str = ""
    description: str = ""
    category: str = "build"
    duration_days: int = 30
    task_type: str = "binary"
    scene_template: str = ""
    icon: str = "🎯"
    color: str = "#FF8A65"
    plan: list[dict[str, object]] = Field(default_factory=list)
    original_creator: bool = True


class ImportResponse(BaseModel):
    id: int
    title: str
    message: str = "导入成功"
