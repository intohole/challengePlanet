from __future__ import annotations

SPORT_MET: dict[str, float] = {
    "walking": 4.3,
    "running": 9.8,
    "cycling": 7.5,
    "jump_rope": 11.8,
    "swimming": 8.0,
    "strength": 5.0,
    "fitness": 6.0,
    "yoga": 3.0,
}

SPORT_LABEL: dict[str, str] = {
    "walking": "快走",
    "running": "跑步",
    "cycling": "骑行",
    "jump_rope": "跳绳",
    "swimming": "游泳",
    "strength": "力量训练",
    "fitness": "综合健身",
    "yoga": "瑜伽",
}


def calc_calories(met: float, weight_kg: float, minutes: float) -> float:
    if met <= 0 or weight_kg <= 0 or minutes <= 0:
        return 0.0
    return round(met * weight_kg * minutes / 60.0, 1)