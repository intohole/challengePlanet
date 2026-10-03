from __future__ import annotations


from pydantic import BaseModel


class PointsSummaryResponse(BaseModel):
    total: int = 0
    week_points: int = 0
    week_key: str = ""


