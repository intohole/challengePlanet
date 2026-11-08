from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.schemas.challenge import ChallengeResponse
from app.services.absence_service import assess_absence
from app.services.challenge_present import (
    CATEGORY_META,
    build_today_payload,
    calc_progress as _calc_progress,
    normalize_title as _normalize_title,
    parse_plan as _parse_plan_impl,
    parse_start_date as _parse_start_date_impl,
    to_challenge_response,
)
from app.services.forecast_service import ForecastService
from app.services.goal_rule_service import is_cap_mode
from app.services.journey_service import JourneyService
from app.services.mercy_service import MercyService, load_valid_dates
from app.services.rescue_service import assess_rescue
from app.services.period_service import week_aggregates
from app.services.slip_service import assess_slip
from app.services.streak_service import (
    calc_streak,
    shift_date,
    silent_kept_of,
    streak_before,
    today_str,
)
from app.services.target_service import TargetService

logger = logging.getLogger(__name__)

__all__ = ["ChallengeService", "CATEGORY_META", "_normalize_title"]


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
        task_type: str = "binary",
        scene_template: str = "", target_value: float = 1.0, unit: str = "次",
        direction: str = "increase", goal_type: str = "hard",
        decompose_mode: str = "none", goal_rule: str = "fixed",
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
            "source": source, "extra": "{}",
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
            from app.services.graduation_service import graduation_goal_day
            from app.services.streak_service import day_number_of
            goal_day = graduation_goal_day(challenge)
            day_number = day_number_of(str(challenge.start_date), today) if goal_day else 0
            if goal_day and day_number >= goal_day:
                challenge.status = "graduated"
            else:
                challenge.status = "completed"
            closed += 1
        if closed:
            await session.commit()
        return closed

    async def close_resting(self, session: AsyncSession) -> int:
        """失踪越过 SUNSET 线的 active 挑战迁入 resting（r26 诚实终局）。

        判定单源 touch_gate_service.episode_over（与触达 gate 同一语义，防两处漂移）：
        最后一次在场日（load_valid_dates 含冻结/修复/护盾）超 30 天 = 这段旅程告一段落。
        从未在场（无 valid 日期）不判——尚未启程不是失踪（对齐 assess_absence 前提）。
        幂等：resting 的挑战不再出现在 active 扫描里，重复执行恒 0。
        """
        from app.services.touch_gate_service import effective_anchor, episode_over
        from app.services.streak_service import day_number_of
        from app.services.graduation_service import graduation_goal_day

        today = today_str()
        rested = 0
        for challenge in await self._repo.get_all_active(session):
            valid_dates = await load_valid_dates(session, int(challenge.id))
            if not valid_dates:
                continue
            last_seen = effective_anchor(max(valid_dates), str(challenge.start_date or ""))
            if not episode_over(last_seen, today):
                continue
            goal_day = graduation_goal_day(challenge)
            if goal_day and day_number_of(str(challenge.start_date), today) >= goal_day:
                continue
            challenge.status = "resting"
            logger.info(
                "challenge rested: id=%s user=%s title=%s last_seen=%s",
                challenge.id, challenge.user_id, challenge.title, last_seen,
            )
            rested += 1
        if rested:
            await session.commit()
        return rested

    async def revive_challenge(
        self, session: AsyncSession, challenge_id: int, user_id: str,
    ) -> dict[str, object] | None:
        """resting 挑战重新出发：新 episode 从今天起算（计划期重开，历史打卡保留）。

        TouchState 一并清除——触达 gate 的发送钟/缺席钟锚旧 episode，不清会让
        复活后的首条触达被旧时钟判 revive/silence（新 episode 应从 first_touch 起步）。
        """
        from app.models.reminder import TouchState
        from sqlalchemy import delete as sa_delete

        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        if challenge.status != "resting":
            return {"revived": False, "reason": f"status={challenge.status}"}
        today = today_str()
        challenge.status = "active"
        challenge.start_date = today
        challenge.end_date = shift_date(today, max(int(challenge.duration_days or 30) - 1, 1))
        await session.execute(
            sa_delete(TouchState).where(
                TouchState.user_id == str(user_id),
                TouchState.challenge_id == int(challenge_id),
            )
        )
        await session.commit()
        logger.info(
            "challenge revived: id=%s user=%s new_start=%s end=%s",
            challenge_id, user_id, today, challenge.end_date,
        )
        return {"revived": True, "start_date": today, "end_date": challenge.end_date}

    async def get_challenge(self, session: AsyncSession, challenge_id: int) -> Challenge | None:
        return await self._repo.get_by_id(session, challenge_id)

    async def delete_challenge(
        self, session: AsyncSession, challenge_id: int, user_id: str,
        mode: str = "archive",
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return None
        if mode == "purge":
            await self._repo.delete_with_children(session, challenge.id)
            await session.commit()
            return {"deleted": True, "status": "purged", "message": "挑战已彻底删除"}
        from app.services.archive_service import archive_and_delete
        summary = await archive_and_delete(session, challenge)
        await session.commit()
        return {
            "deleted": True, "status": "archived", "message": "旅程已封存，战绩计入累计",
            "archived": summary,
        }

    async def get_challenge_stats(
        self, session: AsyncSession, challenge: Challenge,
        valid_dates: set[str] | None = None,
    ) -> dict[str, int]:
        valid = valid_dates if valid_dates is not None else await load_valid_dates(session, challenge.id)
        completed = (sum(1 for d in valid if d < today_str()) if is_cap_mode(challenge)
                     else await self._checkin_repo.count_active_days(session, challenge.id))
        checkin_rows = await self._checkin_repo.get_by_challenge(session, challenge.id)
        checkin_dates = {str(c.date) for c in checkin_rows}
        return {
            "completed_days": completed,
            "total_days": challenge.duration_days,
            "streak": calc_streak(valid, today_str()),
            "silent_kept": silent_kept_of(valid, checkin_dates, today_str()),
            "last_streak": streak_before(valid, shift_date(max(valid), 1)) if valid else 0,
        }

    async def build_list_item(
        self, session: AsyncSession, challenge: Challenge, user_id: str,
    ) -> dict[str, object]:
        valid_dates = await load_valid_dates(session, challenge.id)
        stats = await self.get_challenge_stats(session, challenge, valid_dates=valid_dates)
        today_checkin = await self._checkin_repo.get_by_date(session, challenge.id, today_str())
        mercy = await MercyService().get_mercy_status(session, challenge.id, user_id)
        meta = await self._meta_repo.get(session, challenge.id)
        rescue = assess_rescue(
            challenge, valid_dates, today_str(), today_checkin is not None,
        )
        return {
            "challenge": challenge, "stats": stats,
            "today_checked": today_checkin is not None,
            "source": meta.source if meta else "manual",
            "task_type": challenge.task_type,
            "scene_template": challenge.scene_template,
            "rescue": rescue,
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
        return to_challenge_response(challenge, item)

    def _parse_start_date(self, raw: str | None) -> datetime | None:
        return _parse_start_date_impl(raw)

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
            day_number=day_number or None,
        )
        period_days = max(1, int(getattr(challenge, "period_days", 7) or 7))
        aggregates = await week_aggregates(session, challenge_id, today_checkins, period_days)
        stats = await self.get_challenge_stats(session, challenge)
        progress = _calc_progress(stats["completed_days"], challenge.duration_days)
        journey_rows = await self._checkin_repo.get_daily_totals(
            session, challenge_id, start_date.date().isoformat(), now_dt.date().isoformat(),
        )
        journey = await JourneyService().build(
            session, challenge, max(1, day_number), start_date.date(), now_dt.date(),
            rows=journey_rows,
        )
        slip = assess_slip(challenge, journey_rows, today) if day_number >= 2 else None
        if slip is not None:
            slip["today_checked"] = len(today_checkins) > 0
            slip["can_shift"] = challenge.status == "active"
        absence = assess_absence(challenge, journey_rows, today) if day_number >= 2 else None
        if absence is not None:
            absence["today_checked"] = len(today_checkins) > 0
            absence["can_shift"] = challenge.status == "active"
        from app.services.return_service import active_return_state

        return_state = await active_return_state(session, challenge, today)
        return build_today_payload(
            challenge, challenge_id, day_number, today, task,
            today_checkins, today_total, today_target, dynamic_baseline,
            stats, progress, aggregates, forecast, journey, slip, absence,
            return_state=return_state,
        )

    def _parse_plan(self, ai_plan: str | None) -> list[dict[str, object]]:
        return _parse_plan_impl(ai_plan)
