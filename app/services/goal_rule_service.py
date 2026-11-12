from __future__ import annotations

from nexus import loads_or

_MAX_ADJUSTMENTS = 12
_MAX_SHIFT = 31


def parse_ladder_adjustments(raw: object) -> list[dict[str, int]]:
    if isinstance(raw, (list, tuple)):
        items: list[object] = list(raw)
    else:
        loaded = loads_or(str(raw or ""), [])
        items = loaded if isinstance(loaded, list) else []
    out: list[dict[str, int]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            day = int(it.get("day") or 0)
            shift = int(it.get("shift") or 0)
        except (TypeError, ValueError):
            continue
        if day >= 2 and 0 < shift <= _MAX_SHIFT:
            out.append({"day": day, "shift": shift})
    out.sort(key=lambda a: a["day"])
    return out


def total_shift_days(adjustments: list[dict[str, int]]) -> int:
    return sum(int(a["shift"]) for a in adjustments)


def shifted_day(day_number: int, adjustments: list[dict[str, int]]) -> int:
    day = int(day_number)
    for adj in reversed(adjustments):
        if day >= adj["day"]:
            day -= adj["shift"]
    return max(1, day)


def is_ladder(challenge: object) -> bool:
    return str(getattr(challenge, "goal_rule", "") or "") == "ladder"


def is_cap_mode(challenge: object) -> bool:
    return (
        str(getattr(challenge, "direction", "") or "") == "decrease"
        and str(getattr(challenge, "task_type", "") or "") in ("counter", "timer")
    )


def is_adaptive(challenge: object) -> bool:
    return str(getattr(challenge, "goal_rule", "") or "") == "adaptive"


def resolve_mode(challenge: object) -> str:
    mode = str(getattr(challenge, "goal_mode", "auto") or "auto")
    if mode not in ("ceiling", "floor", "range"):
        return "ceiling" if challenge.direction == "decrease" else "floor"
    return mode


def is_repeatable(challenge: object) -> bool:
    if str(getattr(challenge, "decompose_mode", "") or "") == "time_slot":
        return True
    return str(getattr(challenge, "task_type", "") or "") in ("counter", "timer", "diet", "step")


def ladder_cap_of(
    direction: str, start: float, goal: float,
    interval: int, step: float, day_number: int,
) -> float:
    if step <= 0:
        step = 1.0
    elapsed = (day_number - 1) // max(1, interval)
    if direction == "decrease":
        return max(goal, start - elapsed * step)
    if goal <= 0:
        return start + elapsed * step
    return min(goal, start + elapsed * step)


def restart_anchor_of(challenge: object) -> dict[str, float | str] | None:
    """重启重锚（r27）：ladder_restart JSON {"date","cap"}——从该日起曲线以 cap 为新起点重走。

    缺席长归来的「不可能任务」根治：阶梯按日历走到毕业底时，回来的人面对做不到的
    上限。重锚让 cap 从他上次真实守住的量重新递减，锚前曲线字节级不变。
    """
    from nexus import loads_or

    raw = str(getattr(challenge, "ladder_restart", "") or "")
    if not raw:
        return None
    loaded = loads_or(raw, {})
    if not isinstance(loaded, dict):
        return None
    try:
        cap = float(loaded.get("cap") or 0)
    except (TypeError, ValueError):
        return None
    date = str(loaded.get("date") or "")
    start = str(getattr(challenge, "start_date", "") or "")
    if cap <= 0 or not date or not start or date < start:
        return None
    return {"date": date, "cap": cap}


def _anchor_day_number(challenge: object, anchor_date: str) -> int:
    from datetime import datetime as _dt

    start = str(getattr(challenge, "start_date", "") or "")
    try:
        s = _dt.strptime(start, "%Y-%m-%d").date()
        d = _dt.strptime(anchor_date, "%Y-%m-%d").date()
    except ValueError:
        return 0
    return max(1, (d - s).days + 1)


def ladder_cap_with(
    challenge: object, day_number: int, adjustments: list[dict[str, int]],
) -> float:
    direction = str(getattr(challenge, "direction", "") or "increase")
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    interval = max(1, int(getattr(challenge, "ladder_interval", 1) or 1))
    step = float(getattr(challenge, "ladder_step", 1) or 1)
    shifted = shifted_day(day_number, adjustments)
    anchor = restart_anchor_of(challenge)
    if anchor is not None:
        anchor_shifted = shifted_day(_anchor_day_number(challenge, str(anchor["date"])), adjustments)
        if shifted >= anchor_shifted:
            return ladder_cap_of(
                direction, float(anchor["cap"]), goal, interval, step,
                shifted - anchor_shifted + 1,
            )
    return ladder_cap_of(direction, start, goal, interval, step, shifted)


def ladder_cap(challenge: object, day_number: int) -> float:
    return ladder_cap_with(
        challenge, day_number,
        parse_ladder_adjustments(getattr(challenge, "ladder_adjust", "")),
    )


def present_start_of(challenge: object, day_number: int) -> tuple[float, bool]:
    """重锚生效后的呈现起点与 restarted 标志：锚后日 ladder_start 以 anchor.cap
    为准（r27 遗留③——任务卡「12→3」徽章在重锚后语义过期），锚前/未重锚返回原始起点。"""
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    anchor = restart_anchor_of(challenge)
    if anchor is None:
        return start, False
    adj = parse_ladder_adjustments(getattr(challenge, "ladder_adjust", ""))
    anchor_shifted = shifted_day(_anchor_day_number(challenge, str(anchor["date"])), adj)
    if day_number >= anchor_shifted:
        return float(anchor["cap"]), True
    return start, False


def ladder_goal_day_with(challenge: object, adjustments: list[dict[str, int]]) -> int | None:
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    if start <= 0 or goal >= start:
        return None
    step = float(getattr(challenge, "ladder_step", 1) or 1) or 1.0
    interval = max(1, int(getattr(challenge, "ladder_interval", 1) or 1))
    plain = int(-(-(start - goal) // step)) * interval + 1
    limit = plain + total_shift_days(adjustments) + interval + 2
    anchor = restart_anchor_of(challenge)
    first_day = 2
    if anchor is not None:
        anchor_day = _anchor_day_number(challenge, str(anchor["date"]))
        anchor_shifted = shifted_day(anchor_day, adjustments)
        span_a = abs(float(anchor["cap"]) - goal)
        anchor_plain = int(-(-span_a // step)) * interval + 1
        limit = max(limit, anchor_shifted + anchor_plain + interval + 2)
        first_day = max(first_day, anchor_day)
    for day in range(first_day, limit + 1):
        if ladder_cap_with(challenge, day, adjustments) <= goal + 1e-9:
            return day
    return None


def ladder_goal_day(challenge: object) -> int | None:
    return ladder_goal_day_with(
        challenge, parse_ladder_adjustments(getattr(challenge, "ladder_adjust", "")),
    )


def dynamic_baseline_from(avg: float | None, challenge: object) -> float:
    target = float(getattr(challenge, "target_value", 1.0) or 1.0)
    if avg is None or avg <= 0:
        return max(target, 1.0)
    if str(getattr(challenge, "direction", "") or "increase") == "decrease":
        return round(max(avg * 0.9, max(target * 0.5, 1.0)), 2)
    return round(max(avg * 1.1, 1.0), 2)


def daily_target(
    challenge: object,
    day_number: int,
    adaptive_baseline: float | None = None,
) -> float:
    if is_ladder(challenge):
        return ladder_cap(challenge, day_number)
    if is_adaptive(challenge) and adaptive_baseline is not None:
        return adaptive_baseline
    return float(getattr(challenge, "target_value", 1.0) or 1.0)


def plan_day_target(challenge: object, day_number: int, fallback: float | None = None) -> float:
    plan = getattr(challenge, "ai_plan", None)
    if isinstance(plan, str):
        try:
            import json

            plan = json.loads(plan)
        except ValueError:
            plan = None
    if not isinstance(plan, list) or not 0 < day_number <= len(plan):
        return fallback if fallback is not None else 0.0
    entry = plan[day_number - 1]
    try:
        value = float((entry or {}).get("target_value") or 0)
    except (TypeError, ValueError, AttributeError):
        value = 0.0
    if value <= 0:
        return fallback if fallback is not None else 0.0
    return value


def ladder_meta(challenge: object) -> dict[str, float | int | str]:
    return {
        "ladder_start": float(getattr(challenge, "ladder_start", 0) or 0),
        "ladder_goal": float(getattr(challenge, "ladder_goal", 0) or 0),
        "ladder_interval": max(1, int(getattr(challenge, "ladder_interval", 1) or 1)),
        "ladder_step": float(getattr(challenge, "ladder_step", 1) or 1),
    }


def ladder_progress_pct(challenge: object, day_number: int) -> float:
    meta = ladder_meta(challenge)
    start = meta["ladder_start"]
    goal = meta["ladder_goal"]
    cap = ladder_cap(challenge, day_number)
    if challenge.direction == "decrease":
        start, _restarted = present_start_of(challenge, day_number)
        span = start - goal
        if span <= 0:
            return 100.0
        return max(0.0, min((start - cap) / span * 100.0, 100.0))
    if span <= 0:
        return 100.0
    return max(0.0, min((cap - start) / (goal - start) * 100.0, 100.0))


def judge_mode(challenge: object, task_type: str) -> str:
    if task_type in ("diet", "text"):
        return "record_done"
    if str(getattr(challenge, "direction", "") or "increase") == "decrease":
        return "record_done" if task_type == "binary" else "cap_kept"
    return "target_met"


def is_win_settled(
    mode: str, total: float, target: float, has_record: int,
    day_open: bool = True,
) -> bool:
    if mode == "record_done":
        return has_record > 0
    if mode == "cap_kept":
        if day_open:
            return False
        return total <= target
    return target > 0 and total >= target


def is_settled(challenge: object, task_type: str, today_total: float, today_target: float, has_record: int) -> bool:
    return is_win_settled(
        judge_mode(challenge, task_type), today_total, today_target, has_record,
        day_open=True,
    )


def is_period_settled(challenge: object, task_type: str, period_total: float, period_target: float, has_record: int) -> bool:
    if period_target <= 0:
        return False
    return is_win_settled(
        judge_mode(challenge, task_type), period_total, period_target, has_record,
        day_open=False,
    )