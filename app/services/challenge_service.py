from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.services.ai_service import AIService
from app.services.mercy_service import MercyService, load_valid_dates
from app.services.streak_service import calc_streak, today_str

logger = get_logger("challengePlanet.challenge")

CATEGORY_META: dict[str, dict[str, str]] = {
    "quit": {"icon": "🚭", "color": "#ef4444", "label": "戒除"},
    "build": {"icon": "🌱", "color": "#10b981", "label": "培养"},
    "learn": {"icon": "📚", "color": "#6366f1", "label": "学习"},
    "fitness": {"icon": "💪", "color": "#f59e0b", "label": "运动"},
    "mind": {"icon": "🧠", "color": "#8b5cf6", "label": "心智"},
    "other": {"icon": "🎯", "color": "#8b5cf6", "label": "其他"},
}

SOURCE_LIFECOMPASS = "lifecompass"


class ChallengeService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._ai = AIService()

    async def create_with_plan(
        self,
        session: AsyncSession,
        user_id: str,
        title: str,
        description: str,
        category: str,
        duration_days: int,
        start_date: str,
        plan: list[dict[str, object]],
        source: str = "manual",
        squad_id: int | None = None,
        task_type: str = "binary",
        scene_template: str = "",
    ) -> Challenge:
        meta = CATEGORY_META.get(category, CATEGORY_META["other"])
        if start_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now()
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = (start_dt + timedelta(days=duration_days - 1)).strftime("%Y-%m-%d")
        challenge = await self._repo.create(session, {
            "user_id": user_id,
            "title": title,
            "description": description,
            "category": category,
            "duration_days": duration_days,
            "start_date": start_str,
            "end_date": end_str,
            "status": "active",
            "ai_plan": json.dumps(plan, ensure_ascii=False),
            "color": meta["color"],
            "icon": meta["icon"],
            "task_type": task_type,
            "scene_template": scene_template,
            "share_token": secrets.token_hex(16),
        })
        await self._meta_repo.upsert(session, challenge.id, {
            "source": source,
            "squad_id": squad_id,
            "extra": "{}",
        })
        return challenge

    async def create_from_decision(
        self,
        session: AsyncSession,
        user_id: str,
        title: str,
        description: str,
        duration_days: int,
    ) -> Challenge:
        plan_data = await self._ai.generate_challenge_plan(title, description, "other", duration_days)
        plan = plan_data.get("plan", [])
        if not isinstance(plan, list):
            plan = []
        return await self.create_with_plan(
            session, user_id, title, description, "other", duration_days, "",
            [dict(item) for item in plan if isinstance(item, dict)],
            source=SOURCE_LIFECOMPASS,
        )

    async def get_user_challenges(self, session: AsyncSession, user_id: str) -> list[Challenge]:
        return await self._repo.get_by_user_id(session, user_id)

    async def get_challenge(self, session: AsyncSession, challenge_id: int) -> Challenge | None:
        return await self._repo.get_by_id(session, challenge_id)

    async def get_challenge_stats(
        self, session: AsyncSession, challenge: Challenge
    ) -> dict[str, int]:
        checkins = await self._checkin_repo.get_by_challenge(session, challenge.id)
        valid = await load_valid_dates(session, challenge.id)
        return {
            "completed_days": len(checkins),
            "total_days": challenge.duration_days,
            "streak": calc_streak(valid, today_str()),
        }

    async def build_list_item(
        self, session: AsyncSession, challenge: Challenge, user_id: str
    ) -> dict[str, object]:
        stats = await self.get_challenge_stats(session, challenge)
        today_checkin = await self._checkin_repo.get_by_date(session, challenge.id, today_str())
        mercy = await MercyService().get_mercy_status(session, challenge.id, user_id)
        meta = await self._meta_repo.get(session, challenge.id)
        return {
            "challenge": challenge,
            "stats": stats,
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

    async def get_today_task(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        day_number = (datetime.now() - start_date).days + 1
        day_number = max(1, min(day_number, challenge.duration_days))
        try:
            plan_list: list[dict[str, object]] = json.loads(challenge.ai_plan) if challenge.ai_plan else []
        except json.JSONDecodeError:
            plan_list = []
        task: dict[str, object] = {}
        if plan_list and day_number <= len(plan_list):
            task = plan_list[day_number - 1]
        today = today_str()
        today_checkin = await self._checkin_repo.get_by_date(session, challenge_id, today)
        stats = await self.get_challenge_stats(session, challenge)
        progress = (stats["completed_days"] / challenge.duration_days * 100) if challenge.duration_days > 0 else 0
        task_steps_raw = task.get("steps", task.get("task_steps", []))
        task_steps = task_steps_raw if isinstance(task_steps_raw, list) else []
        return {
            "challenge_id": challenge_id,
            "day_number": day_number,
            "date": today,
            "task": task,
            "task_title": str(task.get("title", "")),
            "task_description": str(task.get("description", "")),
            "task_tip": str(task.get("tip", "")),
            "task_type": str(task.get("task_type", challenge.task_type)),
            "task_target": float(task.get("target_value", task.get("target", 0))),
            "task_unit": str(task.get("unit", "")),
            "task_steps": task_steps,
            "checked_in": today_checkin is not None,
            "checkin_data": {
                "mood": today_checkin.mood,
                "reflection": today_checkin.reflection,
                "ai_feedback": today_checkin.ai_feedback,
            } if today_checkin else None,
            "streak": stats["streak"],
            "total_checkins": stats["completed_days"],
            "progress_pct": round(progress, 1),
        }

    async def get_portal_today(
        self, session: AsyncSession, user_id: str
    ) -> dict[str, object]:
        challenges = await self._repo.get_active_by_user_id(session, user_id)
        today = today_str()
        items: list[dict[str, object]] = []
        for challenge in challenges:
            checked = await self._checkin_repo.get_by_date(session, challenge.id, today)
            detail = await self.get_today_task(session, challenge.id, user_id)
            items.append({
                "challenge_id": challenge.id,
                "title": challenge.title,
                "icon": challenge.icon,
                "color": challenge.color,
                "checked": checked is not None,
                "today_task_title": str((detail or {}).get("task_title", "")),
            })
        pending = sum(1 for item in items if not item["checked"])
        return {"date": today, "pending_count": pending, "items": items}

    async def get_share_data(
        self, session: AsyncSession, challenge_id: int
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None:
            return None
        return await self._build_share_data(session, challenge)

    async def get_share_data_by_token(
        self, session: AsyncSession, share_token: str
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_share_token(session, share_token)
        if challenge is None:
            return None
        return await self._build_share_data(session, challenge)

    async def _build_share_data(
        self, session: AsyncSession, challenge: Challenge
    ) -> dict[str, object]:
        stats = await self.get_challenge_stats(session, challenge)
        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        current_day = min((datetime.now() - start_date).days + 1, challenge.duration_days)
        progress = (stats["completed_days"] / challenge.duration_days * 100) if challenge.duration_days > 0 else 0
        share_quote = await self._get_or_create_quote(session, challenge, stats["streak"])
        share_text = (
            f"🎯 {challenge.title}\n"
            f"已坚持 {stats['completed_days']}/{challenge.duration_days} 天 ({progress:.0f}%)\n"
            f"🔥 连续 {stats['streak']} 天\n"
            f"在挑战星球，用AI规划每一天的坚持"
        )
        return {
            "challenge_id": challenge.id,
            "title": challenge.title,
            "duration_days": challenge.duration_days,
            "current_day": current_day,
            "total_checkins": stats["completed_days"],
            "streak": stats["streak"],
            "progress_pct": round(progress, 1),
            "share_text": share_text,
            "share_token": challenge.share_token,
            "share_quote": share_quote,
        }

    async def _get_or_create_quote(
        self, session: AsyncSession, challenge: Challenge, streak: int
    ) -> str:
        meta = await self._meta_repo.get(session, challenge.id)
        cached: dict[str, object] = {}
        if meta is not None and meta.extra:
            try:
                cached = json.loads(meta.extra)
            except json.JSONDecodeError:
                cached = {}
        quote = str(cached.get("share_quote", ""))
        if quote:
            return quote
        try:
            quote = await self._ai.generate_share_quote(challenge.title, streak)
        except Exception as e:
            logger.warning("share quote fallback: %s", e)
            quote = "坚持，是最好的答案"
        cached["share_quote"] = quote
        await self._meta_repo.upsert(session, challenge.id, {"extra": json.dumps(cached, ensure_ascii=False)})
        return quote
