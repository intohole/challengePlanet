from __future__ import annotations

import asyncio
from datetime import datetime

from nexus.logging import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkin import CheckIn, AIInsight
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.repositories.squad_repository import SquadRepository
from app.repositories.sub_goal_repository import SubGoalRepository
from app.services.adaptive_service import evaluate_after_bad_mood_task
from app.services.checkin_background import (
    fill_ai_after_checkin,
    generate_weekly_report_task,
    save_memory,
)
from app.services.goal_rule_service import daily_target, is_ladder
from app.services.mercy_service import load_valid_dates
from app.services.points_service import PointsService
from app.services.shield_service import ShieldService
from app.services.streak_service import calc_streak, today_str, week_dates_of

logger = get_logger("challengePlanet.checkin")

_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro: object) -> None:
    task = asyncio.create_task(coro)  # type: ignore[arg-type]
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class CheckInService:
    def __init__(self, points: PointsService | None = None) -> None:
        self._repo = CheckInRepository()
        self._insight_repo = InsightRepository()
        self._challenge_repo = ChallengeRepository()
        self._sub_goal_repo = SubGoalRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._squad_repo = SquadRepository()
        self._points = points or PointsService()
        self._shields = ShieldService()

    async def do_checkin(
        self,
        session: AsyncSession,
        challenge_id: int,
        user_id: str,
        value: float = 1.0,
        mood: str = "",
        reflection: str = "",
        sub_goal_id: int | None = None,
        context_tag: str = "",
        timestamp: datetime | None = None,
    ) -> dict[str, object]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")

        ts = timestamp or datetime.now()
        today = ts.strftime("%Y-%m-%d")
        hhmm = ts.strftime("%H:%M")

        if sub_goal_id is None and challenge.decompose_mode == "time_slot":
            sub_goal = await self._sub_goal_repo.get_by_time_window(session, challenge_id, hhmm)
            if sub_goal is not None:
                sub_goal_id = sub_goal.id

        start_dt = datetime.strptime(challenge.start_date, "%Y-%m-%d") if challenge.start_date else ts
        day_number = max(1, min((ts.date() - start_dt.date()).days + 1, challenge.duration_days))

        target_snapshot = await self._compute_target_snapshot(session, challenge, sub_goal_id, day_number)

        completion_pct = self._calc_completion_pct(value, target_snapshot["target_value"], challenge.direction)
        if str(getattr(challenge, "task_type", "")) == "diet" and target_snapshot["target_value"] > 0:
            from app.services.diet_service import assess_calorie
            assess = assess_calorie(value, target_snapshot["target_value"])
            completion_pct = 100.0 if assess["status"] == "ok" else min(90.0, max(30.0, float(assess["percent"])))
        is_soft_exceeded = self._is_soft_exceeded(value, target_snapshot, challenge)
        soft_exceeded_amount = max(0.0, value - target_snapshot["target_value"]) if is_soft_exceeded else 0.0

        checkin = await self._repo.create(session, {
            "challenge_id": challenge_id, "user_id": user_id,
            "sub_goal_id": sub_goal_id, "day_number": day_number,
            "status": "completed", "timestamp": ts, "date": today,
            "value": value, "unit": challenge.unit,
            "target_value": target_snapshot["target_value"],
            "goal_type": target_snapshot["goal_type"],
            "direction": challenge.direction,
            "completion_pct": completion_pct,
            "mood": mood, "reflection": reflection,
            "context_tag": context_tag,
        })

        today_total = await self._repo.sum_value_by_date(session, challenge_id, today)
        remaining = self._calc_remaining(today_total, target_snapshot["target_value"], challenge.direction)
        streak = await self._current_streak(session, challenge_id)
        base, chest = await self._points.award_checkin(
            session, user_id, challenge_id, streak,
            mini=False, completion_pct=completion_pct,
        )
        shields = await self._shields.award_milestone(session, challenge_id, streak)
        await self._maybe_award_squad_bonus(session, challenge_id, today)
        _fire_and_forget(fill_ai_after_checkin(
            checkin.id, user_id, challenge.title, day_number,
            challenge.duration_days, mood, reflection, value,
            target_snapshot["target_value"], challenge.direction,
            is_soft_exceeded,
        ))
        _fire_and_forget(save_memory(user_id, challenge.title, day_number, mood, reflection, value))
        if mood == "bad":
            _fire_and_forget(evaluate_after_bad_mood_task(challenge_id))
        if day_number % 7 == 0 or day_number == challenge.duration_days:
            _fire_and_forget(generate_weekly_report_task(challenge_id))

        return {
            "checkin": checkin, "ai_feedback": "",
            "points_earned": base, "chest_points": chest,
            "streak": streak, "already_checked": False,
            "declaration": "", "shields": shields,
            "today_total": today_total, "today_target": target_snapshot["target_value"],
            "today_cap": target_snapshot["target_value"],
            "goal_rule": str(challenge.goal_rule) or "fixed",
            "dynamic_baseline": target_snapshot["target_value"],
            "remaining": remaining, "is_soft_exceeded": is_soft_exceeded,
            "soft_exceeded_amount": soft_exceeded_amount,
        }

    async def _compute_target_snapshot(
        self, session: AsyncSession, challenge, sub_goal_id: int | None,
        day_number: int,
    ) -> dict[str, object]:
        if str(getattr(challenge, "task_type", "")) == "diet":
            return {
                "target_value": float(getattr(challenge, "daily_calorie_target", 0) or 0),
                "goal_type": "soft",
            }
        if is_ladder(challenge):
            return {
                "target_value": daily_target(challenge, day_number),
                "goal_type": challenge.goal_type,
            }
        if sub_goal_id is not None:
            sub_goal = await self._sub_goal_repo.get_by_id(session, sub_goal_id)
            if sub_goal is not None and sub_goal.challenge_id == challenge.id:
                target = sub_goal.target_value if sub_goal.target_value > 0 else challenge.slot_target_value
                goal_type = sub_goal.goal_type
                if target <= 0:
                    target = await self._dynamic_baseline(session, challenge)
                    goal_type = challenge.goal_type
                return {"target_value": target, "goal_type": goal_type}
        if challenge.decompose_mode == "time_slot" and challenge.slot_target_value > 0:
            return {"target_value": challenge.slot_target_value, "goal_type": challenge.goal_type}
        baseline = await self._dynamic_baseline(session, challenge)
        return {"target_value": baseline, "goal_type": challenge.goal_type}

    async def _dynamic_baseline(self, session: AsyncSession, challenge) -> float:
        recent = await self._repo.list_recent(session, challenge.id, days=7)
        if not recent:
            return max(challenge.target_value, 1.0)
        daily_totals: dict[str, float] = {}
        for c in recent:
            daily_totals[c.date] = daily_totals.get(c.date, 0.0) + c.value
        if not daily_totals:
            return max(challenge.target_value, 1.0)
        avg = sum(daily_totals.values()) / len(daily_totals)
        if challenge.direction == "decrease":
            return max(avg * 0.9, max(challenge.target_value * 0.5, 1.0))
        return max(avg * 1.1, 1.0)

    def _calc_completion_pct(self, value: float, target: float, direction: str) -> float:
        if target <= 0:
            return 100.0
        if direction == "decrease":
            return min(max(0.0, (target - value) / target * 100 + 100), 100.0) if value > target else 100.0
        return min(value / target * 100, 100.0)

    def _is_soft_exceeded(self, value: float, target_snapshot: dict[str, object], challenge) -> bool:
        target = float(target_snapshot.get("target_value", 0))
        goal_type = str(target_snapshot.get("goal_type", "hard"))
        if goal_type != "soft" or target <= 0:
            return False
        return value > target

    def _calc_remaining(self, today_total: float, today_target: float, direction: str) -> float:
        return max(0.0, today_target - today_total)

    async def _maybe_award_squad_bonus(
        self, session: AsyncSession, challenge_id: int, today: str,
    ) -> None:
        meta = await self._meta_repo.get(session, challenge_id)
        if meta is None or meta.squad_id is None:
            return
        members = await self._squad_repo.get_members(session, meta.squad_id)
        if not members:
            return
        for member in members:
            checked = await self._repo.user_has_checkin_on_date(session, member.user_id, today)
            if not checked:
                return
        await self._points.award_squad_bonus(
            session, [m.user_id for m in members], meta.squad_id, today
        )

    async def _current_streak(self, session: AsyncSession, challenge_id: int) -> int:
        valid = await load_valid_dates(session, challenge_id)
        return calc_streak(valid, today_str())

    async def update_today_reflection(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        mood: str, reflection: str,
    ) -> CheckIn:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        today = today_str()
        checkin = await self._repo.get_by_date(session, challenge_id, today)
        if checkin is None:
            raise ValueError("今日还未打卡")
        updated = await self._repo.update(session, checkin, {
            "mood": mood, "reflection": reflection,
        })
        _fire_and_forget(fill_ai_after_checkin(
            checkin.id, user_id, challenge.title,
            checkin.day_number, challenge.duration_days,
            mood, reflection, checkin.value, checkin.target_value,
            challenge.direction, False,
        ))
        _fire_and_forget(
            save_memory(user_id, challenge.title, checkin.day_number, mood, reflection, checkin.value)
        )
        if mood == "bad":
            _fire_and_forget(evaluate_after_bad_mood_task(challenge_id))
        return updated

    async def delete_checkin(
        self, session: AsyncSession, checkin_id: int, user_id: str,
    ) -> None:
        result = await session.execute(
            select(CheckIn).where(CheckIn.id == checkin_id, CheckIn.user_id == user_id)
        )
        checkin = result.scalar_one_or_none()
        if checkin is None:
            raise ValueError("打卡记录不存在")
        await self._repo.delete(session, checkin)

    async def get_checkins(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> list[CheckIn]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return await self._repo.get_by_challenge(session, challenge_id)

    async def get_today_checkins(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> list[CheckIn]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return await self._repo.list_by_date(session, challenge_id, today_str())

    async def get_insights(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> list:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return await self._insight_repo.get_by_challenge(session, challenge_id)

    async def get_weekly_report(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> dict[str, object]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        insight = await self._insight_repo.get_latest_weekly(session, challenge_id)
        checkins = await self._repo.get_by_challenge(session, challenge_id)
        week_dates = set(week_dates_of())
        week_count = sum(1 for c in checkins if c.date in week_dates)
        return {
            "report": insight.content if insight else "",
            "generated_at": insight.created_at if insight else None,
            "week_checkins": week_count, "week_days": 7,
        }
