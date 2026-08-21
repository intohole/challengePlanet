from __future__ import annotations


def is_ladder(challenge: object) -> bool:
    return str(getattr(challenge, "goal_rule", "") or "") == "ladder"


def is_adaptive(challenge: object) -> bool:
    return str(getattr(challenge, "goal_rule", "") or "") == "adaptive"


def resolve_mode(challenge: object) -> str:
    mode = str(getattr(challenge, "goal_mode", "auto") or "auto")
    if mode not in ("ceiling", "floor", "range"):
        return "ceiling" if challenge.direction == "decrease" else "floor"
    return mode


def ladder_cap(challenge: object, day_number: int) -> float:
    start = float(getattr(challenge, "ladder_start", 0) or 0)
    goal = float(getattr(challenge, "ladder_goal", 0) or 0)
    interval = max(1, int(getattr(challenge, "ladder_interval", 1) or 1))
    step = float(getattr(challenge, "ladder_step", 1) or 1)
    if step <= 0:
        step = 1.0
    elapsed = (day_number - 1) // interval
    if challenge.direction == "decrease":
        return max(goal, start - elapsed * step)
    if goal <= 0:
        return start + elapsed * step
    return min(goal, start + elapsed * step)


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