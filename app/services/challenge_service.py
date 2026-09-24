from __future__ import annotations

import json
import logging
import re
import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.schemas.challenge import ChallengeResponse
from app.services.ai_text_sanitizer import sanitize_coach_text
from app.services.forecast_service import ForecastService
from app.services.goal_rule_service import is_cap_mode, is_ladder, is_repeatable, is_settled, ladder_progress_pct, resolve_mode
from app.services.mercy_service import MercyService, load_valid_dates
from app.services.period_service import period_fields, week_aggregates
from app.services.streak_service import calc_streak, shift_date, streak_before, today_str
from app.services.target_service import TargetService

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


def _calc_progress(completed_days: int, duration_days: int) -> float:
    if duration_days <= 0:
        return 0.0
    return round(completed_days * 100.0 / duration_days, 1)


def _normalize_title(raw: str) -> str:
    t = (raw or "").strip().strip('"\'“”‘’「」『』【】')
    t = re.split(r"[，,。；;！!？?、]", t, maxsplit=1)[0].strip()
    for suffix in _STATUS_SUFFIXES:
        if t.endswith(suffix):
            t = t[: -len(suffix)].rstrip("，,、 ")
            break
    return t[:12] or "我的挑战"


class ChallengeService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._targets = TargetService()

    async def create_with_plan(
        self, session: AsyncSession, user_id: str, title: str, description: str,
        category: str, duration_days: int, start_date: str,
        plan: list[dict[str, object]], source: str = "manual",
        squad_id: int | None = None, task_type: str = "binary",
        scene_template: str = "", target_value: float = 1.0, unit: str = "次",
        direction: str = "increase", goal_type: str = "hard",
        decompose_mode: str = "none", slot_hours: int = 1,
        slot_target_value: float = 0.0, goal_rule: str = "fixed",
        goal_mode: str = "auto", ladder_start: float = 0.0,
        ladder_goal: float = 0.0, ladder_interval: int = 1,
        ladder_step: float = 1.0, gender: str = "", age: int = 0,
        height_cm: float = 0.0, weight_kg: float = 0.0,
        goal_weight: float = 0.0, activity_level: int = 2,
        period_days: int = 7, period_target: float = 0.0,
        period_unit: str = "", sport_met: float = 0.0,
    ) -> Challenge:
        title = _normalize_title(title)
        meta = CATEGORY_META.get(category, CATEGORY_META["other"])
        start_dt = datetime.strptime(start_date, "%Y-%m-%d") if start_date else now_china()
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = (start_dt + timedelta(days=duration_days - 1)).strftime("%Y-%m-%d")
        daily_calorie_target: float = 0.0
        if task_type == "diet" and weight_kg > 0 and age > 0 and height_cm > 0:
            from app.services.diet_service import calc_daily_target
            cal = calc_daily_target(
                gender, age, height_cm, weight_kg, goal_weight,
                activity_level, duration_days,
            )
            daily_calorie_target = cal["target_kcal"]
        challenge = await self._repo.create(session, {
            "user_id": user_id, "title": title, "description": description,
            "category": category, "duration_days": duration_days,
            "start_date": start_str, "end_date": end_str, "status": "active",
            "ai_plan": json.dumps(plan, ensure_ascii=False),
            "color": meta["color"], "icon": meta["icon"],
            "task_type": task_type, "scene_template": scene_template,
            "target_value": target_value, "unit": unit, "direction": direction,
            "goal_type": goal_type, "goal_rule": goal_rule, "goal_mode": goal_mode,
            "ladder_start": ladder_start, "ladder_goal": ladder_goal,
            "ladder_interval": ladder_interval, "ladder_step": ladder_step,
            "decompose_mode": decompose_mode,
            "slot_hours": slot_hours, "slot_target_value": slot_target_value,
            "gender": gender, "age": age, "height_cm": height_cm,
            "weight_kg": weight_kg, "goal_weight": goal_weight,
            "activity_level": activity_level,
            "daily_calorie_target": daily_calorie_target,
            "period_days": max(1, period_days),
            "period_target": period_target, "period_unit": period_unit,
            "sport_met": sport_met,
            "share_token": secrets.token_hex(16),
        })
        await self._meta_repo.upsert(session, challenge.id, {
            "source": source, "squad_id": squad_id, "extra": "{}",
        })
        await session.commit()
        return challenge

    async def get_user_challenges(self, session: AsyncSession, user_id: str) -> list[Challenge]:
        return await self._repo.get_by_user_id(session, user_id)

    async def close_finished(self, session: AsyncSession) -> int:
        today = today_str()
        closed = 0
        for challenge in await self._repo.get_all_active(session):
            if str(getattr(challenge, "end_date", "") or "") >= today:
                continue
            challenge.status = "completed"
            closed += 1
        if closed:
            await session.commit()
        return closed

    async def get_challenge(self, session: AsyncSession, challenge_id: int) -> Challenge | None:
        return await self._repo.get_by_id(session, challenge_id)

    async def delete_challenge(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        await self._repo.delete_with_children(session, challenge.id)
        await session.commit()
        return {"deleted": True, "status": "deleted", "message": "挑战已删除"}

    async def get_challenge_stats(
        self, session: AsyncSession, challenge: Challenge,
    ) -> dict[str, int]:
        valid = await load_valid_dates(session, challenge.id)
        completed = (sum(1 for d in valid if d < today_str()) if is_cap_mode(challenge)
                     else await self._checkin_repo.count_active_days(session, challenge.id))
        return {
            "completed_days": completed,
            "total_days": challenge.duration_days,
            "streak": calc_streak(valid, today_str()),
            "last_streak": streak_before(valid, shift_date(max(valid), 1)) if valid else 0,
        }

    async def build_list_item(
        self, session: AsyncSession, challenge: Challenge, user_id: str,
    ) -> dict[str, object]:
        stats = await self.get_challenge_stats(session, challenge)
        today_checkin = await self._checkin_repo.get_by_date(session, challenge.id, today_str())
        mercy = await MercyService().get_mercy_status(session, challenge.id, user_id)
        meta = await self._meta_repo.get(session, challenge.id)
        return {
            "challenge": challenge, "stats": stats,
            "today_checked": today_checkin is not None,
            "source": meta.source if meta else "manual",
            "task_type": challenge.task_type,
            "scene_template": challenge.scene_template,
            "mercy": {
                "mend_left_this_month": mercy["mend_left_this_month"],
                "freeze_left_this_week": mercy["freeze_left_this_week"],
                "repair_available": mercy["repair_available"],
            },
        }

    async def build_response(
        self, session: AsyncSession, challenge: object, user_id: str,
    ) -> ChallengeResponse:
        item = await self.build_list_item(session, challenge, user_id)
        return self._to_response(challenge, item)

    def _to_response(self, challenge: object, item: dict[str, object]) -> ChallengeResponse:
        c = challenge
        stats = item["stats"]
        try:
            plan = json.loads(c.ai_plan) if c.ai_plan else []
        except json.JSONDecodeError:
            plan = []
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
            slot_hours=int(getattr(c, "slot_hours", 1) or 1), slot_target_value=float(getattr(c, "slot_target_value", 0.0) or 0.0),
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
            created_at=c.created_at,
        )

    def _parse_start_date(self, raw: str | None) -> datetime | None:
        if not raw:
            return None
        try:
            return datetime.strptime(raw, "%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning("challenge start_date 无法解析: %r", raw)
            return None

    async def get_today_task(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        parsed_start = self._parse_start_date(challenge.start_date)
        if parsed_start is None:
            return None
        start_date: datetime = parsed_start
        now_dt = now_china()
        today = today_str()
        day_number = max(1, min((now_dt - start_date).days + 1, challenge.duration_days))
        if now_dt.date() < start_date.date():
            day_number = 0
        plan_list = self._parse_plan(challenge.ai_plan)
        task = plan_list[day_number - 1] if plan_list and 0 < day_number <= len(plan_list) else {}
        today_checkins = await self._checkin_repo.list_by_date(session, challenge_id, today)
        today_total = await self._checkin_repo.sum_value_by_date(session, challenge_id, today)
        dynamic_baseline = await self._targets.live_baseline(session, challenge)
        snapshot = await self._targets.resolve(
            session, challenge, max(1, day_number), adaptive_baseline=dynamic_baseline,
        )
        today_target = float(snapshot["target_value"])
        forecast = await ForecastService().build(
            session, challenge, today_total, today_target, now_dt.hour,
            day_number=day_number or None, store=False,
        )
        period_days = max(1, int(getattr(challenge, "period_days", 7) or 7))
        aggregates = await week_aggregates(session, challenge_id, today_checkins, period_days)
        sub_goals_list = await self._build_sub_goals(session, challenge, today)
        stats = await self.get_challenge_stats(session, challenge)
        progress = _calc_progress(stats["completed_days"], challenge.duration_days)
        return self._build_today_response(
            challenge, challenge_id, day_number, today, task,
            today_checkins, today_total, today_target, dynamic_baseline,
            sub_goals_list, stats, progress, aggregates, forecast,
        )

    def _parse_plan(self, ai_plan: str | None) -> list[dict[str, object]]:
        if not ai_plan:
            return []
        try:
            plan_list = json.loads(ai_plan)
            return plan_list if isinstance(plan_list, list) else []
        except json.JSONDecodeError:
            return []

    async def _build_sub_goals(
        self, session: AsyncSession, challenge, today: str,
    ) -> list[dict[str, object]]:
        from app.repositories.sub_goal_repository import SubGoalRepository
        sub_goal_repo = SubGoalRepository()
        sub_goals_db = await sub_goal_repo.get_by_challenge(session, challenge.id)
        sub_goals_list: list[dict[str, object]] = []
        for sg in sub_goals_db:
            sg_today_value = await self._checkin_repo.sum_value_by_sub_goal(session, sg.id, today)
            sg_today_list = await self._checkin_repo.list_by_sub_goal(session, sg.id, today)
            sg_target = sg.target_value if sg.target_value > 0 else challenge.slot_target_value
            sg_pct = (sg_today_value / sg_target * 100) if sg_target > 0 else 0.0
            sub_goals_list.append({
                "id": sg.id, "title": sg.title,
                "time_window_start": sg.time_window_start,
                "time_window_end": sg.time_window_end,
                "target_value": sg_target, "goal_type": sg.goal_type,
                "today_value": sg_today_value,
                "today_checkin_count": len(sg_today_list),
                "progress_pct": round(min(sg_pct, 100.0), 1),
            })
        return sub_goals_list

    def _build_today_response(
        self, challenge, challenge_id: int, day_number: int, today: str,
        task: dict[str, object], today_checkins, today_total: float,
        today_target: float, dynamic_baseline: float, sub_goals_list: list,
        stats: dict, progress: float, aggregates: dict[str, object] | None = None,
        forecast: dict[str, object] | None = None,
    ) -> dict[str, object]:
        task_steps_raw = task.get("steps", task.get("task_steps", []))
        task_steps = task_steps_raw if isinstance(task_steps_raw, list) else []
        remaining = max(0.0, today_target - today_total)
        feedback = today_checkins[-1].ai_feedback if today_checkins else ""
        not_started = day_number < 1
        repeatable = is_repeatable(challenge, len(sub_goals_list))
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
                    "sub_goal_id": c.sub_goal_id,
                    "mood": c.mood, "reflection": c.reflection,
                    "context_tag": c.context_tag, "ai_feedback": sanitize_coach_text(c.ai_feedback),
                }
                for c in today_checkins
            ],
            "sub_goals": sub_goals_list, "streak": stats["streak"],
            "total_checkins": stats["completed_days"],
        }

    async def get_portal_today(
        self, session: AsyncSession, user_id: str,
    ) -> dict[str, object]:
        challenges = await self._repo.get_active_by_user_id(session, user_id)
        today = today_str()
        items: list[dict[str, object]] = []
        for challenge in challenges:
            checked = await self._checkin_repo.get_by_date(session, challenge.id, today)
            base_item: dict[str, object] = {
                "challenge_id": challenge.id, "title": challenge.title,
                "icon": challenge.icon, "color": challenge.color,
                "checked": checked is not None,
                "today_task_title": "",
            }
            try:
                detail = await self.get_today_task(session, challenge.id, user_id)
                base_item["today_task_title"] = str((detail or {}).get("task_title", ""))
            except Exception as e:
                logger.warning("portal today 单条挑战构建失败 id=%s: %s", challenge.id, e)
            items.append(base_item)
        pending = sum(1 for item in items if not item["checked"])
        return {"date": today, "pending_count": pending, "items": items}
