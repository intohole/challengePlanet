"""挑战呈现层的纯组装函数（r25 从 challenge_service.py 拆出，零行为变更）。

只做「数据进、payload 出」的映射，不碰 session/仓储——编排留在 ChallengeService。
"""
from __future__ import annotations

import logging
import re
from datetime import datetime

from app.schemas.challenge import ChallengeResponse
from app.services.ai_text_sanitizer import sanitize_coach_text
from app.services.goal_rule_service import (
    is_ladder,
    is_repeatable,
    is_settled,
    ladder_progress_pct,
    resolve_mode,
)
from app.services.period_service import period_fields
from app.services.plan_parser import parse_ai_plan

logger = logging.getLogger(__name__)

CATEGORY_META: dict[str, dict[str, str]] = {
    "quit": {"icon": "🚭", "color": "#ef4444", "label": "戒除"},
    "build": {"icon": "🌱", "color": "#10b981", "label": "培养"},
    "learn": {"icon": "📚", "color": "#6366f1", "label": "学习"},
    "fitness": {"icon": "💪", "color": "#f59e0b", "label": "运动"},
    "mind": {"icon": "🧠", "color": "#8b5cf6", "label": "心智"},
    "other": {"icon": "🎯", "color": "#8b5cf6", "label": "其他"},
}

_STATUS_SUFFIXES: tuple[str, ...] = ("当前", "进行中", "打卡中", "现在", "目前")


def calc_progress(completed_days: int, duration_days: int) -> float:
    if duration_days <= 0:
        return 0.0
    return round(completed_days * 100.0 / duration_days, 1)


def normalize_title(raw: str) -> str:
    t = (raw or "").strip().strip('"\'“”‘’「」『』【】')
    t = re.split(r"[，,。；;！!？?、]", t, maxsplit=1)[0].strip()
    for suffix in _STATUS_SUFFIXES:
        if t.endswith(suffix):
            t = t[: -len(suffix)].rstrip("，,、 ")
            break
    return t[:12] or "我的挑战"


def parse_start_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d")
    except (ValueError, TypeError):
        logger.warning("challenge start_date 无法解析: %r", raw)
        return None


def parse_plan(ai_plan: str | None) -> list[dict[str, object]]:
    return parse_ai_plan(ai_plan)


def to_challenge_response(challenge: object, item: dict[str, object]) -> ChallengeResponse:
    c = challenge
    stats = item["stats"]
    plan = parse_ai_plan(c.ai_plan)
    return ChallengeResponse(
        id=c.id,
        user_id=c.user_id,
        title=c.title,
        description=c.description,
        category=c.category,
        duration_days=c.duration_days,
        total_days=stats["total_days"],
        completed_days=stats["completed_days"],
        streak=stats["streak"],
        silent_kept=int(stats.get("silent_kept", 0)),
        last_streak=stats["last_streak"],
        start_date=c.start_date, end_date=c.end_date, status=c.status,
        ai_plan=plan, color=c.color, icon=c.icon,
        task_type=c.task_type, scene_template=c.scene_template,
        is_shared=c.is_shared, share_token=c.share_token,
        source=str(item.get("source", "manual")),
        today_checked=bool(item.get("today_checked", False)),
        target_value=float(getattr(c, "target_value", 1.0) or 1.0), unit=str(getattr(c, "unit", "次") or "次"),
        direction=str(getattr(c, "direction", "increase") or "increase"), goal_type=str(getattr(c, "goal_type", "hard") or "hard"),
        decompose_mode=str(getattr(c, "decompose_mode", "none") or "none"),
        goal_rule=str(getattr(c, "goal_rule", "fixed") or "fixed"), goal_mode=str(getattr(c, "goal_mode", "auto") or "auto"),
        ladder_start=float(getattr(c, "ladder_start", 0.0) or 0.0), ladder_goal=float(getattr(c, "ladder_goal", 0.0) or 0.0),
        ladder_interval=max(1, int(getattr(c, "ladder_interval", 1) or 1)), ladder_step=float(getattr(c, "ladder_step", 1.0) or 1.0),
        period_days=max(1, int(getattr(c, "period_days", 7) or 7)), period_target=float(getattr(c, "period_target", 0.0) or 0.0),
        period_unit=str(getattr(c, "period_unit", "") or ""), sport_met=float(getattr(c, "sport_met", 0.0) or 0.0),
        gender=str(getattr(c, "gender", "") or ""), age=int(getattr(c, "age", 0) or 0),
        height_cm=float(getattr(c, "height_cm", 0.0) or 0.0), weight_kg=float(getattr(c, "weight_kg", 0.0) or 0.0),
        goal_weight=float(getattr(c, "goal_weight", 0.0) or 0.0), activity_level=int(getattr(c, "activity_level", 2) or 2),
        daily_calorie_target=float(getattr(c, "daily_calorie_target", 0.0) or 0.0),
        mercy=item.get("mercy", {}),
        rescue=item.get("rescue", {}) or {},
        created_at=c.created_at,
    )


def build_today_payload(
    challenge, challenge_id: int, day_number: int, today: str,
    task: dict[str, object], today_checkins, today_total: float,
    today_target: float, dynamic_baseline: float,
    stats: dict, progress: float, aggregates: dict[str, object] | None = None,
    forecast: dict[str, object] | None = None,
    journey: dict[str, object] | None = None,
    slip: dict[str, object] | None = None,
    absence: dict[str, object] | None = None,
    return_state: dict[str, object] | None = None,
) -> dict[str, object]:
    task_steps_raw = task.get("steps", task.get("task_steps", []))
    task_steps = task_steps_raw if isinstance(task_steps_raw, list) else []
    remaining = max(0.0, today_target - today_total)
    feedback = today_checkins[-1].ai_feedback if today_checkins else ""
    not_started = day_number < 1
    repeatable = is_repeatable(challenge)
    ladder_progress = ladder_progress_pct(challenge, day_number) if is_ladder(challenge) else 0.0
    task_type = str(task.get("task_type", challenge.task_type))
    pf = period_fields(challenge, task_type, aggregates or {})
    return {
        "challenge_id": challenge_id, "day_number": day_number, "date": today,
        "not_started": not_started,
        "repeatable": repeatable, "task": task, "task_title": str(task.get("title", "")),
        "task_description": str(task.get("description", "")),
        "task_tip": str(task.get("tip", "")),
        "task_type": str(task.get("task_type", challenge.task_type)),
        "task_target": float(task.get("target_value", task.get("target", 0))),
        "task_unit": str(task.get("unit", "")), "task_steps": task_steps,
        "target_value": float(challenge.target_value),
        "unit": str(challenge.unit), "direction": str(challenge.direction),
        "goal_type": str(challenge.goal_type), "decompose_mode": str(challenge.decompose_mode),
        "goal_rule": str(challenge.goal_rule) or "fixed",
        "goal_mode": resolve_mode(challenge),
        "ladder_start": float(getattr(challenge, "ladder_start", 0.0) or 0.0),
        "ladder_goal": float(getattr(challenge, "ladder_goal", 0.0) or 0.0),
        "ladder_interval": max(1, int(getattr(challenge, "ladder_interval", 1) or 1)),
        "ladder_step": float(getattr(challenge, "ladder_step", 1.0) or 1.0),
        "today_total": today_total, "today_target": today_target, "today_cap": today_target,
        "dynamic_baseline": dynamic_baseline, "remaining": round(remaining, 2), "forecast": forecast,
        "journey": journey,
        "slip": slip,
        "absence": absence,
        "return_state": return_state,
        "progress_pct": round(progress, 1), "ladder_progress_pct": round(ladder_progress, 1),
        "checked_in": len(today_checkins) > 0,
        "settled": False if not_started else is_settled(
            challenge, task_type, today_total, today_target, len(today_checkins),
        ),
        **pf,
        "checkin_data": {
            "mood": today_checkins[-1].mood if today_checkins else "",
            "reflection": today_checkins[-1].reflection if today_checkins else "",
            "ai_feedback": sanitize_coach_text(feedback),
            "declaration": sanitize_coach_text(today_checkins[-1].declaration if today_checkins else ""),
        } if today_checkins else None,
        "today_checkins": [
            {
                "id": c.id, "timestamp": c.timestamp.isoformat(),
                "value": c.value, "unit": c.unit, "calories": float(getattr(c, "calories", 0.0) or 0.0),
                "mood": c.mood, "reflection": c.reflection,
                "context_tag": c.context_tag, "ai_feedback": sanitize_coach_text(c.ai_feedback),
            }
            for c in today_checkins
        ],
        "streak": stats["streak"],
        "silent_kept": int(stats.get("silent_kept", 0)),
        "total_checkins": stats["completed_days"],
    }
