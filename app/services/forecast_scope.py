from __future__ import annotations

DURATION_UNITS = ("分钟", "小时", "分钟数", "min", "minute", "h", "hour")


def supports_forecast(challenge: object) -> bool:
    if str(getattr(challenge, "decompose_mode", "") or "") == "time_slot":
        return False
    task_type = str(getattr(challenge, "task_type", "") or "")
    if task_type == "counter":
        return True
    if task_type == "timer":
        return str(getattr(challenge, "unit", "") or "") in DURATION_UNITS
    return False