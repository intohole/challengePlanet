"""戒烟减量阶梯（quit ladder）的解析与输出规则（从 API 层下沉）。"""
from __future__ import annotations

import re

from nexus.logging import get_logger

from app.schemas.challenge import NLCreateRequest

logger = get_logger("challengePlanet.quit_ladder")

_PAIR_RE = re.compile(
    r"从\s*(?:每天|每日|一天|现在|目前)?\s*(\d+(?:\.\d+)?)\s*(?:根|支|杯|瓶|颗|口|顿|个|次|支)?\s*(?:烟|香烟|戒|减|降|控制)?\s*(?:到|至|戒到|减到|降至)\s*(\d+(?:\.\d+)?)\s*(?:根|支|杯|瓶|颗|口|顿|个|次|支)?"
)
_MAX_RE = re.compile(
    r"(?:每天|每日|一天)\s*(?:最多|控制在|不超过|在)\s*(\d+(?:\.\d+)?)\s*(根|支|杯|瓶|颗|口|顿|个)"
)


def apply_quit_ladder(parsed: dict[str, object], raw_input: str) -> dict[str, object]:
    if str(parsed.get("category", "")) != "quit":
        logger.info("quit-ladder skip: category=%s", parsed.get("category"))
        return parsed
    if str(parsed.get("goal_rule", "")) == "ladder" and float(parsed.get("ladder_start", 0) or 0) > 0:
        return parsed
    duration = max(1, int(parsed.get("duration_days", 30) or 30))
    m = _PAIR_RE.search(raw_input)
    if m is None:
        c = _MAX_RE.search(raw_input)
        if c is None:
            logger.info("quit-ladder skip: no numeric pair raw=%r", raw_input[:40])
            return parsed
        start = float(c.group(1))
        goal = 0.0
    else:
        start = float(m.group(1))
        goal = max(0.0, float(m.group(2)))
    if start <= goal:
        logger.info("quit-ladder skip: start<=goal start=%s goal=%s", start, goal)
        return parsed
    span = start - goal
    if span <= duration:
        interval, step = 1, 1
    else:
        interval, step = max(1, int(-(-span // duration))), 1
    parsed.update({
        "goal_rule": "ladder",
        "goal_mode": "ceiling",
        "ladder_start": start,
        "ladder_goal": goal,
        "ladder_interval": interval,
        "ladder_step": float(step),
        "target_value": float(start),
    })
    logger.info("quit-ladder applied: %s→%s interval=%s step=%s", start, goal, interval, step)
    return parsed


def ladder_out(request: NLCreateRequest, parsed: dict[str, object]) -> dict[str, object]:
    fields_set = getattr(request, "model_fields_set", None)
    client_rule = str(request.goal_rule) if (fields_set and "goal_rule" in fields_set) else ""
    rule = str(client_rule or parsed.get("goal_rule") or "fixed")
    start = float(parsed.get("ladder_start", 0.0) or 0.0)
    goal = float(parsed.get("ladder_goal", 0.0) or 0.0)
    if client_rule == "ladder" or (
        rule == "ladder" and (request.ladder_start > 0 or start > 0)
    ):
        if goal <= 0 and start <= 0:
            goal = request.ladder_goal or float(parsed.get("target_value", 1.0) or 1.0)
        return {
            "goal_rule": "ladder",
            "goal_mode": str(request.goal_mode or parsed.get("goal_mode") or "auto"),
            "ladder_start": request.ladder_start or start or max(goal, request.target_value),
            "ladder_goal": goal,
            "ladder_interval": request.ladder_interval or int(parsed.get("ladder_interval", 1) or 1),
            "ladder_step": request.ladder_step or float(parsed.get("ladder_step", 1.0) or 1.0),
        }
    return {
        "goal_rule": "fixed" if rule == "fixed" else rule,
        "goal_mode": str(request.goal_mode or parsed.get("goal_mode") or "auto"),
        "ladder_start": 0.0, "ladder_goal": 0.0,
        "ladder_interval": 1, "ladder_step": 1.0,
    }


