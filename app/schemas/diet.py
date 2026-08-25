from __future__ import annotations

from pydantic import BaseModel, Field


class DietEstimateRequest(BaseModel):
    description: str = Field(..., description="当日饮食描述")


class DietEstimateResponse(BaseModel):
    total_kcal: float = 0.0
    min_kcal: float = 0.0
    max_kcal: float = 0.0
    confidence: float = 0.0
    items: list[dict[str, object]] = Field(default_factory=list)
    assessment: dict[str, object] = Field(default_factory=dict)
    target_kcal: float = 0.0
    deficit_kcal: float = 0.0
    tdee_kcal: float = 0.0
    bmr_kcal: float = 0.0


class DietTargetResponse(BaseModel):
    target_kcal: float = 0.0
    deficit_kcal: float = 0.0
    tdee_kcal: float = 0.0
    bmr_kcal: float = 0.0
    current_weight: float = 0.0
    goal_weight: float = 0.0


class WeightRecordRequest(BaseModel):
    weight_kg: float = Field(..., description="体重kg")
    date: str = Field("", description="日期 YYYY-MM-DD，默认今天")


class WeightRecordItem(BaseModel):
    date: str
    weight_kg: float
    avg7: float = 0.0
    delta: float = 0.0


class WeightTrendResponse(BaseModel):
    records: list[WeightRecordItem] = Field(default_factory=list)
    latest: dict[str, object] | None = None
    count: int = 0