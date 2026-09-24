from __future__ import annotations

import asyncio
from datetime import datetime

from nexus.logging import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.repositories.squad_repository import SquadRepository
from app.repositories.sub_goal_repository import SubGoalRepository
from app.core.datetime_utils import now_china
from app.services.adaptive_service import evaluate_after_bad_mood_task
from app.services.checkin_background import (
    fill_ai_after_checkin,
    save_memory,
)
from app.services.forecast_service import ForecastService
from app.services.goal_rule_service import is_repeatable
from app.services.mercy_service import load_valid_dates
from app.services.points_service import PointsService
from app.services.shield_service import ShieldService
from app.services.streak_service import calc_streak, today_str
from app.services.target_service import TargetService

logger = get_logger("challengePlanet.checkin")

_background_tasks: set[asyncio.Task] = set()


def _fire_and_forget(coro: object) -> None:
    task = asyncio.create_task(coro)  # type: ignore[arg-type]
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


class CheckInService:
    def __init__(self, points: PointsService | None = None) -> None:
        self._repo = CheckInRepository()
        self._challenge_repo = ChallengeRepository()
        self._sub_goal_repo = SubGoalRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._squad_repo = SquadRepository()
        self._targets = TargetService()
        self._points = points or PointsService()
        self._shields = ShieldService()

    def _assert_open_day(self, challenge: Challenge, timestamp: datetime | None) -> str:
        today = today_str()
        if timestamp is not None and timestamp.strftime("%Y-%m-%d") != today:
            raise ValueError("只能记录今天的打卡，过去的日子请用补签")
        if today < str(getattr(challenge, "start_date", "") or ""):
            raise ValueError(f"挑战将于 {challenge.start_date} 开始，到时再来记录吧")
        if today > str(getattr(challenge, "end_date", "") or ""):
            raise ValueError("挑战已结束，战绩已保留")
        return today

    def _day_number_of(self, challenge: Challenge, today: str) -> int:
        start_dt = datetime.strptime(challenge.start_date, "%Y-%m-%d") if challenge.start_date else now_china()
        day_number = (datetime.strptime(today, "%Y-%m-%d").date() - start_dt.date()).days + 1
        return max(1, min(day_number, challenge.duration_days))

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
        if str(getattr(challenge, "task_type", "")) == "text" and not (reflection or "").strip():
            raise ValueError("记得先写下今日记录内容")

        ts = timestamp or now_china()
        today = self._assert_open_day(challenge, timestamp)
        hhmm = ts.strftime("%H:%M")

        if sub_goal_id is None and challenge.decompose_mode == "time_slot":
            sub_goal = await self._sub_goal_repo.get_by_time_window(session, challenge_id, hhmm)
            if sub_goal is not None:
                sub_goal_id = sub_goal.id

        day_number = self._day_number_of(challenge, today)
        baseline = await self._targets.live_baseline(session, challenge)
        target_snapshot = await self._targets.resolve(
            session, challenge, day_number,
            sub_goal_id=sub_goal_id, adaptive_baseline=baseline,
        )
        today_checkins = await self._repo.list_by_date(session, challenge_id, today)
        if today_checkins and not is_repeatable(challenge):
            return await self._replay_checkin(
                session, challenge, today_checkins[-1], target_snapshot, baseline, day_number,
            )

        completion_pct = self._calc_completion_pct(value, target_snapshot["target_value"], challenge.direction)
        if str(getattr(challenge, "task_type", "")) == "diet" and target_snapshot["target_value"] > 0:
            from app.services.diet_service import assess_calorie
            assess = assess_calorie(value, target_snapshot["target_value"])
            completion_pct = 100.0 if assess["status"] == "ok" else min(90.0, max(30.0, float(assess["percent"])))
        is_soft_exceeded = self._is_soft_exceeded(value, target_snapshot, challenge)
        soft_exceeded_amount = max(0.0, value - target_snapshot["target_value"]) if is_soft_exceeded else 0.0
        calories = 0.0
        sport_met = float(getattr(challenge, "sport_met", 0.0) or 0.0)
        unit = str(getattr(challenge, "unit", "") or "")
        is_time_based = str(getattr(challenge, "task_type", "")) == "timer" or unit in ("分钟", "小时", "分钟数", "min", "minute")
        if sport_met > 0 and float(getattr(challenge, "weight_kg", 0.0) or 0.0) > 0 and is_time_based:
            from app.services.sport_metrics import calc_calories
            calories = calc_calories(sport_met, float(challenge.weight_kg), value)

        checkin = await self._repo.create(session, {
            "challenge_id": challenge_id, "user_id": user_id,
            "sub_goal_id": sub_goal_id, "day_number": day_number,
            "status": "completed", "timestamp": ts, "date": today,
            "value": value, "unit": challenge.unit,
            "calories": calories,
            "target_value": target_snapshot["target_value"],
            "goal_type": target_snapshot["goal_type"],
            "direction": challenge.direction,
            "completion_pct": completion_pct,
            "mood": mood, "reflection": reflection,
            "context_tag": context_tag,
        })

        today_total = await self._repo.sum_value_by_date(session, challenge_id, today)
        remaining = self._calc_remaining(today_total, target_snapshot["target_value"], challenge.direction)
        forecast = await ForecastService().build(
            session, challenge, today_total, target_snapshot["target_value"],
            ts.hour, is_soft_exceeded=is_soft_exceeded, day_number=day_number,
        )
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

        return self._result_payload(
            challenge, checkin, target_snapshot, baseline,
            today_total, remaining, base, chest, streak, shields,
            already_checked=False, is_soft_exceeded=is_soft_exceeded,
            soft_exceeded_amount=soft_exceeded_amount, forecast=forecast,
        )

    async def _replay_checkin(
        self, session: AsyncSession, challenge: Challenge, existing: CheckIn,
        target_snapshot: dict[str, object], baseline: float, day_number: int,
    ) -> dict[str, object]:
        today_total = await self._repo.sum_value_by_date(session, challenge.id, existing.date)
        target = float(target_snapshot["target_value"])
        remaining = self._calc_remaining(today_total, target, challenge.direction)
        forecast = await ForecastService().build(
            session, challenge, today_total, target, now_china().hour,
            day_number=day_number, store=False,
        )
        return self._result_payload(
            challenge, existing, target_snapshot, baseline,
            today_total, remaining, 0, 0,
            await self._current_streak(session, challenge.id),
            await self._shields.get_shields(session, challenge.id),
            already_checked=True, is_soft_exceeded=False,
            soft_exceeded_amount=0.0, forecast=forecast,
        )

    def _result_payload(
        self, challenge: Challenge, checkin: CheckIn,
        target_snapshot: dict[str, object], baseline: float, today_total: float,
        remaining: float, points: int, chest: int, streak: int, shields: int,
        already_checked: bool, is_soft_exceeded: bool,
        soft_exceeded_amount: float, forecast: dict[str, object],
    ) -> dict[str, object]:
        target = float(target_snapshot["target_value"])
        return {
            "checkin": checkin, "ai_feedback": str(checkin.ai_feedback or ""),
            "points_earned": points, "chest_points": chest,
            "streak": streak, "already_checked": already_checked,
            "declaration": str(checkin.declaration or ""), "shields": shields,
            "today_total": today_total, "today_target": target,
            "today_cap": target,
            "goal_rule": str(challenge.goal_rule) or "fixed",
            "dynamic_baseline": baseline,
            "remaining": remaining, "is_soft_exceeded": is_soft_exceeded,
            "soft_exceeded_amount": soft_exceeded_amount,
            "coach_nudge": str(forecast.get("coach_nudge", "")),
            "nudge_level": int(forecast.get("nudge_level", 0)),
            "forecast": forecast,
        }

    def _calc_completion_pct(self, value: float, target: float, direction: str) -> float:
        if target <= 0:
            return 100.0
        if direction == "decrease":
            return 100.0
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
