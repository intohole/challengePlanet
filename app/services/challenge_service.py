from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.schemas.challenge import ChallengeCreate, TodayTaskResponse
from app.services.ai_service import AIService

CATEGORY_META: dict[str, dict[str, str]] = {
    "quit": {"icon": "🚭", "color": "#ef4444", "label": "戒除"},
    "build": {"icon": "🌱", "color": "#10b981", "label": "培养"},
    "learn": {"icon": "📚", "color": "#6366f1", "label": "学习"},
    "fitness": {"icon": "💪", "color": "#f59e0b", "label": "运动"},
    "mind": {"icon": "🧠", "color": "#8b5cf6", "label": "心智"},
    "other": {"icon": "🎯", "color": "#8b5cf6", "label": "其他"},
}


class ChallengeService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._ai = AIService()

    async def get_user_challenges(self, session: AsyncSession, user_id: str) -> list[Challenge]:
        return await self._repo.get_by_user_id(session, user_id)

    async def get_challenge(self, session: AsyncSession, challenge_id: int) -> Challenge | None:
        return await self._repo.get_by_id(session, challenge_id)

    async def get_challenge_stats(
        self, session: AsyncSession, challenge: Challenge
    ) -> dict[str, int]:
        checkins = await self._checkin_repo.get_by_challenge(session, challenge.id)
        streak = self._calc_streak(checkins)
        return {
            "completed_days": len(checkins),
            "total_days": challenge.duration_days,
            "streak": streak,
        }

    async def create_challenge(
        self, session: AsyncSession, request: ChallengeCreate
    ) -> Challenge:
        meta = CATEGORY_META.get(request.category, CATEGORY_META["other"])
        if request.start_date:
            start_dt = datetime.strptime(request.start_date, "%Y-%m-%d")
        else:
            start_dt = datetime.now()
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = (start_dt + timedelta(days=request.duration_days - 1)).strftime("%Y-%m-%d")

        plan_data = await self._ai.generate_challenge_plan(
            request.title, request.description, request.category, request.duration_days
        )
        ai_plan = plan_data.get("plan", [])

        challenge = await self._repo.create(session, {
            "user_id": request.user_id,
            "title": request.title,
            "description": request.description,
            "category": request.category,
            "duration_days": request.duration_days,
            "start_date": start_str,
            "end_date": end_str,
            "status": "active",
            "ai_plan": json.dumps(ai_plan, ensure_ascii=False),
            "color": meta["color"],
            "icon": meta["icon"],
            "share_token": secrets.token_hex(16),
        })
        await session.commit()
        return challenge

    async def create_from_nl(
        self, session: AsyncSession, user_id: str, parsed: dict[str, object], start_date: str
    ) -> Challenge:
        title = str(parsed.get("title", "未命名挑战"))
        category = str(parsed.get("category", "other"))
        duration = int(parsed.get("duration_days", 30))
        description = str(parsed.get("description", ""))
        return await self.create_challenge(session, ChallengeCreate(
            user_id=user_id,
            title=title,
            description=description,
            category=category,
            duration_days=duration,
            start_date=start_date,
        ))

    async def get_today_task(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> TodayTaskResponse | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None:
            return None

        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        day_number = (datetime.now() - start_date).days + 1
        if day_number < 1:
            day_number = 1
        if day_number > challenge.duration_days:
            day_number = challenge.duration_days

        try:
            plan_list: list[dict[str, object]] = json.loads(challenge.ai_plan) if challenge.ai_plan else []
        except json.JSONDecodeError:
            plan_list = []

        task: dict[str, object] = {}
        if plan_list and day_number <= len(plan_list):
            task = plan_list[day_number - 1]

        checkins = await self._checkin_repo.get_by_challenge(session, challenge_id)
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_checkin = await self._checkin_repo.get_by_date(session, challenge_id, today_str)

        streak = self._calc_streak(checkins)
        progress = (len(checkins) / challenge.duration_days * 100) if challenge.duration_days > 0 else 0

        return TodayTaskResponse(
            challenge_id=challenge_id,
            day_number=day_number,
            date=today_str,
            task=task,
            task_title=str(task.get("title", "")),
            task_description=str(task.get("description", "")),
            task_tip=str(task.get("tip", "")),
            checked_in=today_checkin is not None,
            checkin_data={
                "mood": today_checkin.mood,
                "reflection": today_checkin.reflection,
                "ai_feedback": today_checkin.ai_feedback,
            } if today_checkin else None,
            streak=streak,
            total_checkins=len(checkins),
            progress_pct=round(progress, 1),
        )

    def _calc_streak(self, checkins: list) -> int:
        if not checkins:
            return 0
        dates = sorted([c.date for c in checkins])
        today = datetime.now().strftime("%Y-%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        if today not in dates and yesterday not in dates:
            return 0
        streak = 0
        check_date = today if today in dates else yesterday
        while check_date in dates:
            streak += 1
            prev = datetime.strptime(check_date, "%Y-%m-%d") - timedelta(days=1)
            check_date = prev.strftime("%Y-%m-%d")
        return streak

    async def get_share_data(
        self, session: AsyncSession, challenge_id: int
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None:
            return None
        checkins = await self._checkin_repo.get_by_challenge(session, challenge_id)
        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        current_day = min((datetime.now() - start_date).days + 1, challenge.duration_days)
        streak = self._calc_streak(checkins)
        progress = (len(checkins) / challenge.duration_days * 100) if challenge.duration_days > 0 else 0
        share_text = (
            f"🎯 {challenge.title}\n"
            f"已坚持 {len(checkins)}/{challenge.duration_days} 天 ({progress:.0f}%)\n"
            f"🔥 连续 {streak} 天\n"
            f"在挑战星球，用AI规划每一天的坚持"
        )
        return {
            "challenge_id": challenge_id,
            "title": challenge.title,
            "duration_days": challenge.duration_days,
            "current_day": current_day,
            "total_checkins": len(checkins),
            "streak": streak,
            "progress_pct": round(progress, 1),
            "share_text": share_text,
            "share_token": challenge.share_token,
        }
