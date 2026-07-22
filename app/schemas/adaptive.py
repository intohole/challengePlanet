from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AdaptiveTask(BaseModel):
    day: int = 0
    title: str = ""
    description: str = ""
    tip: str = ""


class AdaptiveSuggestionResponse(BaseModel):
    id: int
    kind: str = "lighten"
    reason: str = ""
    task: AdaptiveTask
    target_day: int = 0
    created_at: Optional[datetime] = None


class AdaptivePendingResponse(BaseModel):
    suggestion: Optional[AdaptiveSuggestionResponse] = None


class AdaptiveRespondRequest(BaseModel):
    accept: bool = Field(..., description="是否采纳建议")


class AdaptiveRespondResponse(BaseModel):
    ok: bool = False
    applied: bool = False
    task: Optional[AdaptiveTask] = None


class DiagnoseResponse(BaseModel):
    cause: str = ""
    cause_label: str = ""
    narrative: str = ""
    suggestion_action: str = "keep"
    suggestion_text: str = ""
    missed_count: int = 0
    done_days: int = 0
    total_days: int = 0
    report_id: int = 0


class DiagnosisLatestResponse(BaseModel):
    report: Optional[DiagnoseResponse] = None


class DiagnoseApplyRequest(BaseModel):
    action: str = Field(..., description="应用方案: lighten3/micro/keep")


class DiagnoseApplyResponse(BaseModel):
    ok: bool = False
    message: str = ""
    adjusted_days: int = 0
