from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.repositories.checkin_repository import CheckInRepository
from app.services.goal_rule_service import (
    daily_target,
    dynamic_baseline_from,
    is_adaptive,
    is_ladder,
)

BASELINE_DAYS = 7


async def recent_daily_avg(
    session: AsyncSession, challenge_id: int, days: int = BASELINE_DAYS,
    end_date: str | None = None,
) -> float | None:
    end = end_date or (now_china().date() - timedelta(days=1)).strftime("%Y-%m-%d")
    start = (datetime.strptime(end, "%Y-%m-%d") - timedelta(days=max(1, days) - 1)).strftime("%Y-%m-%d")
    rows = await CheckInRepository().get_daily_totals(session, challenge_id, start, end)
    values = [float(row["value"]) for row in rows if float(row["value"]) > 0]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


class TargetService:
    async def live_baseline(self, session: AsyncSession, challenge: object) -> float:
        avg = await recent_daily_avg(session, getattr(challenge, "id"))
        return dynamic_baseline_from(avg, challenge)

    async def resolve(
        self, session: AsyncSession, challenge: object, day_number: int,
        adaptive_baseline: float | None = None,
    ) -> dict[str, object]:
        task_type = str(getattr(challenge, "task_type", "") or "")
        goal_type = str(getattr(challenge, "goal_type", "hard") or "hard")
        if task_type == "diet":
            return {
                "target_value": float(getattr(challenge, "daily_calorie_target", 0) or 0),
                "goal_type": "soft",
            }
        if is_ladder(challenge):
            return {"target_value": daily_target(challenge, day_number), "goal_type": goal_type}
        if is_adaptive(challenge) and adaptive_baseline is None:
            adaptive_baseline = await self.live_baseline(session, challenge)
        return {
            "target_value": daily_target(challenge, day_number, adaptive_baseline=adaptive_baseline),
            "goal_type": goal_type,
        }
