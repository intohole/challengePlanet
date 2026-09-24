from __future__ import annotations


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


def is_repeatable(challenge: object, sub_goals_count: int = 0) -> bool:
    if sub_goals_count > 0:
        return True
    if str(getattr(challenge, "decompose_mode", "") or "") == "time_slot":
        return True
    return str(getattr(challenge, "task_type", "") or "") in ("counter", "timer")


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


def ladder_cap(challenge: object, day_number: int) -> float:
    return ladder_cap_of(
        str(getattr(challenge, "direction", "") or "increase"),
        float(getattr(challenge, "ladder_start", 0) or 0),
        float(getattr(challenge, "ladder_goal", 0) or 0),
        max(1, int(getattr(challenge, "ladder_interval", 1) or 1)),
        float(getattr(challenge, "ladder_step", 1) or 1),
        day_number,
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


def is_ceiling_met(challenge: object, today_total: float, day_number: int) -> bool:
    return today_total <= daily_target(challenge, day_number)


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
    span = start - goal
    if challenge.direction == "decrease":
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