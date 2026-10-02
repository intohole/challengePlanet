from __future__ import annotations

from datetime import datetime

from nexus.logging import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.core.datetime_utils import now_china
from app.services.adaptive_service import evaluate_after_bad_mood_task
from app.services.checkin_background import (
    fire_and_forget,
    save_memory,
)
from app.services.checkin_calc import (
    calc_completion_pct,
    calc_remaining,
    calc_sport_calories,
    is_soft_exceeded,
)
from app.services.forecast_math import CONTEXT_TAGS
from app.services.forecast_service import ForecastService
from app.services.goal_rule_service import is_repeatable
from app.services.mercy_service import load_valid_dates
from app.services.points_service import PointsService
from app.services.prompts import MOODS
from app.services.shield_service import ShieldService
from app.services.streak_service import calc_streak, today_str
from app.services.target_service import TargetService

logger = get_logger("challengePlanet.checkin")


class CheckInService:
    def __init__(self, points: PointsService | None = None) -> None:
        self._repo = CheckInRepository()
        self._challenge_repo = ChallengeRepository()
        self._meta_repo = ChallengeMetaRepository()
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
        context_tag: str = "",
        timestamp: datetime | None = None,
        sport_type: str = "",
        sport_minutes: float = 0.0,
    ) -> dict[str, object]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        if str(getattr(challenge, "task_type", "")) == "text" and not (reflection or "").strip():
            raise ValueError("记得先写下今日记录内容")

        ts = timestamp or now_china()
        today = self._assert_open_day(challenge, timestamp)

        day_number = self._day_number_of(challenge, today)
        baseline = await self._targets.live_baseline(session, challenge)
        target_snapshot = await self._targets.resolve(
            session, challenge, day_number, adaptive_baseline=baseline,
        )
        today_checkins = await self._repo.list_by_date(session, challenge_id, today)
        if today_checkins and not is_repeatable(challenge):
            return await self._replay_checkin(
                session, challenge, today_checkins[-1], target_snapshot, baseline, day_number,
            )

        is_diet = str(getattr(challenge, "task_type", "")) == "diet"
        prior_total = await self._repo.sum_value_by_date(session, challenge_id, today) if is_diet else 0.0
        intake_total = prior_total + value
        sport_minutes_v = float(sport_minutes or 0.0)
        sport_calories = 0.0
        if is_diet and sport_minutes_v > 0:
            sport_calories = calc_sport_calories(challenge, sport_type, sport_minutes_v)
        if is_diet and value <= 0 and sport_minutes_v <= 0:
            raise ValueError("记录内容不能为空")
        burn_total = await self._repo.sum_calories_by_date(session, challenge_id, today) if is_diet else 0.0
        completion_pct = calc_completion_pct(value, target_snapshot["target_value"], challenge.direction)
        if is_diet and target_snapshot["target_value"] > 0:
            from app.services.diet_service import assess_calorie
            assess = assess_calorie(
                intake_total - burn_total - sport_calories, target_snapshot["target_value"],
            )
            completion_pct = 100.0 if assess["status"] == "ok" else min(90.0, max(30.0, float(assess["percent"])))
        gauge_value = intake_total if is_diet else value
        soft_exceeded = is_soft_exceeded(gauge_value, target_snapshot)
        soft_exceeded_amount = max(0.0, gauge_value - target_snapshot["target_value"]) if soft_exceeded else 0.0
        if is_diet and sport_calories > 0 and not (reflection or "").strip():
            from app.services.sport_metrics import SPORT_LABEL
            reflection = f"运动：{SPORT_LABEL.get(sport_type, sport_type)} {sport_minutes_v:g} 分钟"
        calories = sport_calories
        if not is_diet:
            sport_met = float(getattr(challenge, "sport_met", 0.0) or 0.0)
            unit = str(getattr(challenge, "unit", "") or "")
            is_time_based = str(getattr(challenge, "task_type", "")) == "timer" or unit in ("分钟", "小时", "分钟数", "min", "minute")
            if sport_met > 0 and float(getattr(challenge, "weight_kg", 0.0) or 0.0) > 0 and is_time_based:
                from app.services.sport_metrics import calc_calories
                calories = calc_calories(sport_met, float(challenge.weight_kg), value)

        checkin = await self._repo.create(session, {
            "challenge_id": challenge_id, "user_id": user_id,
            "day_number": day_number,
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
        remaining = calc_remaining(today_total, target_snapshot["target_value"])
        forecast = await ForecastService().build(
            session, challenge, today_total, target_snapshot["target_value"],
            ts.hour, is_soft_exceeded=soft_exceeded, day_number=day_number,
        )
        streak = await self._current_streak(session, challenge_id)
        base, chest = await self._points.award_checkin(
            session, user_id, challenge_id, streak,
            mini=False, completion_pct=completion_pct,
        )
        shields = await self._shields.award_milestone(session, challenge_id, streak)
        fire_and_forget(save_memory(user_id, challenge.title, day_number, mood, reflection, value))
        if mood == "bad":
            fire_and_forget(evaluate_after_bad_mood_task(challenge_id))

        return self._result_payload(
            challenge, checkin, target_snapshot, baseline,
            today_total, remaining, base, chest, streak, shields,
            already_checked=False, is_soft_exceeded=soft_exceeded,
            soft_exceeded_amount=soft_exceeded_amount, forecast=forecast,
        )

    async def _replay_checkin(
        self, session: AsyncSession, challenge: Challenge, existing: CheckIn,
        target_snapshot: dict[str, object], baseline: float, day_number: int,
    ) -> dict[str, object]:
        today_total = await self._repo.sum_value_by_date(session, challenge.id, existing.date)
        target = float(target_snapshot["target_value"])
        remaining = calc_remaining(today_total, target)
        forecast = await ForecastService().build(
            session, challenge, today_total, target, now_china().hour,
            day_number=day_number,
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
        fields: dict[str, object] = {"reflection": reflection}
        if mood:
            fields["mood"] = mood
        updated = await self._repo.update(session, checkin, fields)
        fire_and_forget(
            save_memory(user_id, challenge.title, checkin.day_number, mood, reflection, checkin.value)
        )
        if mood == "bad":
            fire_and_forget(evaluate_after_bad_mood_task(challenge_id))
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

    async def update_checkin_meta(
        self, session: AsyncSession, challenge_id: int, checkin_id: int,
        user_id: str, context_tag: str = "", mood: str = "",
    ) -> CheckIn:
        if context_tag == "" and mood == "":
            raise ValueError("没有需要补充的内容")
        if context_tag and context_tag not in CONTEXT_TAGS:
            raise ValueError("情境标签无效")
        if mood and mood not in MOODS:
            raise ValueError("心情标签无效")
        result = await session.execute(
            select(CheckIn).where(
                CheckIn.id == checkin_id,
                CheckIn.challenge_id == challenge_id,
                CheckIn.user_id == user_id,
            )
        )
        checkin = result.scalar_one_or_none()
        if checkin is None:
            raise ValueError("打卡记录不存在")
        if checkin.date != today_str():
            raise ValueError("只能补充今天记录的打卡")
        updates: dict[str, str] = {}
        if context_tag:
            updates["context_tag"] = context_tag
        if mood:
            updates["mood"] = mood
        updated = await self._repo.update(session, checkin, updates)
        if mood == "bad":
            fire_and_forget(evaluate_after_bad_mood_task(challenge_id))
        return updated

    async def get_checkins(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> list[CheckIn]:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return await self._repo.get_by_challenge(session, challenge_id)
