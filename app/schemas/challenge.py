from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PlanDay(BaseModel):
    day: int = Field(..., description="第几天")
    title: str = Field("", description="任务标题")
    description: str = Field("", description="具体任务")
    tip: str = Field("", description="小贴士")


class NLCreateRequest(BaseModel):
    raw_input: str = Field(..., description="自然语言描述, 如: 我想30天戒烟")
    start_date: str = Field("", description="开始日期 YYYY-MM-DD, 空则今天开始")


class ChallengeConfirmRequest(BaseModel):
    title: str = Field(..., description="挑战标题")
    category: str = Field("build", description="分类: quit/build/learn/fitness/mind/other")
    duration_days: int = Field(30, description="挑战天数")
    start_date: str = Field("", description="开始日期 YYYY-MM-DD, 空则今天开始")
    description: str = Field("", description="挑战描述")
    plan: list[PlanDay] = Field(default_factory=list, description="前端预览确认后的计划")
    source: str = Field("manual", description="来源: manual/lifecompass")
    squad_id: Optional[int] = Field(None, description="关联小队ID")


class FromDecisionRequest(BaseModel):
    title: str = Field(..., description="挑战标题")
    description: str = Field("", description="挑战描述")
    duration_days: int = Field(66, description="挑战天数")


class MercySummary(BaseModel):
    mend_left_this_month: int = 0
    freeze_left_this_week: int = 0
    repair_available: bool = False


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
    source: str = "manual"
    today_checked: bool = False
    mercy: MercySummary = Field(default_factory=MercySummary)
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


class WeeklyReportResponse(BaseModel):
    report: str = ""
    generated_at: Optional[datetime] = None
    week_checkins: int = 0
    week_days: int = 7


class PortalTodayItem(BaseModel):
    challenge_id: int
    title: str
    icon: str = "🎯"
    color: str = "#6366f1"
    checked: bool = False
    today_task_title: str = ""


class PortalTodayResponse(BaseModel):
    date: str
    pending_count: int = 0
    items: list[PortalTodayItem] = Field(default_factory=list)


class ShareDataResponse(BaseModel):
    challenge_id: int
    title: str
    duration_days: int
    current_day: int
    total_checkins: int
    streak: int
    progress_pct: float
    share_text: str
    share_token: str
    share_quote: str = ""
