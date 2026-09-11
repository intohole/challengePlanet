from __future__ import annotations

from app.services.goal_rule_service import is_period_settled
from app.services.streak_service import week_dates_of


async def week_aggregates(session: object, challenge_id: int, today_checkins: list) -> dict[str, object]:
    from app.repositories.checkin_repository import CheckInRepository
    dates = sorted(week_dates_of())
    checkins = await CheckInRepository().list_by_date_range(session, challenge_id, dates[0], dates[-1])
    return {
        "week_total": sum(float(c.value or 0.0) for c in checkins),
        "calories_today": sum(float(getattr(c, "calories", 0.0) or 0.0) for c in today_checkins),
        "calories_week": sum(float(getattr(c, "calories", 0.0) or 0.0) for c in checkins),
        "week_has_record": len(checkins) > 0,
    }


def period_fields(challenge: object, task_type: str, agg: dict[str, object]) -> dict[str, object]:
    period_target = float(getattr(challenge, "period_target", 0.0) or 0.0)
    period_days = max(1, int(getattr(challenge, "period_days", 7) or 7))
    period_unit = str(getattr(challenge, "period_unit", "") or "") or str(getattr(challenge, "unit", "") or "")
    is_kcal = period_unit in ("千卡", "kcal")
    period_total = float(agg.get("calories_week", 0.0)) if is_kcal else float(agg.get("week_total", 0.0))
    return {
        "period_days": period_days,
        "period_target": period_target,
        "period_unit": period_unit,
        "period_total": round(period_total, 1),
        "week_total": round(float(agg.get("week_total", 0.0)), 1),
        "week_target": period_target,
        "week_settled": is_period_settled(
            challenge, task_type, period_total,
            period_target, 1 if agg.get("week_has_record") else 0,
        ),
        "calories_today": round(float(agg.get("calories_today", 0.0)), 1),
        "calories_week": round(float(agg.get("calories_week", 0.0)), 1),
    }