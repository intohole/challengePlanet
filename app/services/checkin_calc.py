from __future__ import annotations

from app.models.challenge import Challenge


def calc_sport_calories(challenge: Challenge, sport_type: str, minutes: float) -> float:
    from app.services.sport_metrics import SPORT_MET, calc_calories
    met = SPORT_MET.get(sport_type, 0.0)
    if met <= 0:
        raise ValueError("请选择有效的运动类型")
    weight_kg = float(getattr(challenge, "weight_kg", 0.0) or 0.0)
    if weight_kg <= 0:
        raise ValueError("缺少体重信息，无法折算运动消耗")
    return calc_calories(met, weight_kg, minutes)


def calc_completion_pct(value: float, target: float, direction: str) -> float:
    if target <= 0:
        return 100.0
    if direction == "decrease":
        return 100.0
    return min(value / target * 100, 100.0)


def is_soft_exceeded(value: float, target_snapshot: dict[str, object]) -> bool:
    target = float(target_snapshot.get("target_value", 0))
    goal_type = str(target_snapshot.get("goal_type", "hard"))
    if goal_type != "soft" or target <= 0:
        return False
    return value > target


def calc_remaining(today_total: float, today_target: float) -> float:
    return max(0.0, today_target - today_total)
