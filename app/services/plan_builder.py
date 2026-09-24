from __future__ import annotations

from app.services.goal_rule_service import ladder_cap_of

_FILL_VARIANTS: tuple[str, str, str] = (
    "挑战真正开始前的最后一轮热身，用小行动找回对目标的掌控感",
    "换个角度推进目标，把今天的任务拆成更小的一个动作先做起来",
    "给自己设置一个小小的奖励仪式，完成后记录这一刻的感受",
)

_MILESTONE_DAYS: set[int] = {7, 14, 21, 28}


def _daily_target(
    day: int, task_type: str, target_value: float,
    direction: str, goal_rule: str, ladder_start: float,
    ladder_goal: float, ladder_interval: int, ladder_step: float,
) -> float:
    if task_type in ("binary", "text", "diet"):
        return 0.0
    if goal_rule == "ladder" and ladder_start > 0:
        return ladder_cap_of(
            direction, ladder_start, ladder_goal,
            max(1, ladder_interval), ladder_step, day,
        )
    return float(target_value) if target_value > 0 else 0.0


def _derive_item(
    day: int, title: str, duration: int,
    task_type: str, target_value: float, unit: str, steps: list[str],
) -> dict[str, object]:
    item: dict[str, object] = {
        "day": day,
        "title": title,
        "task_type": task_type,
        "target_value": target_value,
        "unit": unit,
        "difficulty": 1,
        "steps": steps,
    }
    if day in _MILESTONE_DAYS or day == duration:
        item["title"] = f"阶段小结：回看前{day}天"
        item["description"] = f"回顾这{day}天的进展，写下做得最好的1件事和明天要突破的1个点"
        item["tip"] = "里程碑不追求量，而在于看见自己的变化"
        item["difficulty"] = 1
        return item
    var = _FILL_VARIANTS[(day - 1) % len(_FILL_VARIANTS)]
    item["description"] = f"坚持{title}。今日重心：{var}"
    item["tip"] = "保持自己的节奏"
    item["difficulty"] = max(1, min(5, 1 + ((day - 1) * 4 + (duration - 1)) // max(duration, 2)))
    return item


def build_plan(
    title: str,
    duration: int,
    *,
    task_type: str = "binary",
    target_value: float = 0.0,
    unit: str = "",
    direction: str = "increase",
    goal_rule: str = "fixed",
    ladder_start: float = 0.0,
    ladder_goal: float = 0.0,
    ladder_interval: int = 1,
    ladder_step: float = 1.0,
    steps: list[str] | None = None,
) -> dict[str, object]:
    duration = max(1, int(duration or 1))
    clean_steps = [str(s) for s in (steps or []) if s]
    plan: list[dict[str, object]] = []
    for day in range(1, duration + 1):
        tv = _daily_target(
            day, task_type, target_value, direction, goal_rule,
            ladder_start, ladder_goal, max(1, ladder_interval), ladder_step,
        )
        plan.append(_derive_item(day, title, duration, task_type, tv, unit, clean_steps))
    return {
        "plan": plan,
        "suggestions": [
            "每天按时打卡，先完成再完美",
            "记录真实感受，回看时更有力量",
            "允许偶尔不稳，重要的是持续",
        ],
    }