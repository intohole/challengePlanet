from __future__ import annotations

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import StreakActionRepository
from app.services.ai_service import AIService
from app.services.points_service import PointsService
from app.services.streak_service import (
    calc_streak,
    day_number_of,
    list_missed_dates,
    month_prefix_of,
    shift_date,
    streak_before,
    today_str,
    week_dates_of,
)

logger = get_logger("challengePlanet.mercy")

FREE_MEND_PER_MONTH = 2
MEND_COST = 50
FREE_FREEZE_PER_WEEK = 1
FREEZE_COST = 20
REPAIR_LIMIT_PER_MONTH = 1
ACTION_MEND = "mend"
ACTION_FREEZE = "freeze"
ACTION_REPAIR = "repair"


async def load_valid_dates(session: AsyncSession, challenge_id: int) -> set[str]:
    checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
    actions = await StreakActionRepository().get_by_challenge(session, challenge_id)
    dates = {c.date for c in checkins}
    for action in actions:
        if action.action in (ACTION_FREEZE, ACTION_REPAIR):
            dates.add(action.action_date)
    return dates


class MercyService:
    def __init__(self, points: PointsService | None = None) -> None:
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._action_repo = StreakActionRepository()
        self._points = points or PointsService()
        self._ai = AIService()

    async def _get_owned_challenge(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> Challenge:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return challenge

    async def _valid_dates(self, session: AsyncSession, challenge_id: int) -> set[str]:
        return await load_valid_dates(session, challenge_id)

    async def mend(
        self, session: AsyncSession, challenge_id: int, user_id: str, target_date: str
    ) -> dict[str, object]:
        challenge = await self._get_owned_challenge(session, challenge_id, user_id)
        today = today_str()
        if target_date >= today:
            raise ValueError("只能补签过去的日期")
        if target_date < challenge.start_date or target_date > challenge.end_date:
            raise ValueError("只能补签挑战期间内的日期")
        existing = await self._checkin_repo.get_by_date(session, challenge_id, target_date)
        if existing is not None:
            raise ValueError("该日期已有打卡记录")

        month_prefix = month_prefix_of()
        used = await self._action_repo.count_user_actions_in_month(
            session, user_id, ACTION_MEND, month_prefix
        )
        cost = 0
        if used >= FREE_MEND_PER_MONTH:
            ok = await self._points.spend(session, user_id, MEND_COST, ACTION_MEND, str(challenge_id))
            if not ok:
                raise ValueError(f"免费补签卡已用完，积分不足{MEND_COST}分")
            cost = MEND_COST

        day_number = day_number_of(challenge.start_date, target_date)
        await self._checkin_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "day_number": day_number,
            "date": target_date,
            "status": "mended",
            "mood": "",
            "reflection": "",
            "ai_feedback": "",
        })
        await self._action_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "action": ACTION_MEND,
            "action_date": target_date,
            "cost": cost,
        })
        valid = await self._valid_dates(session, challenge_id)
        return {"date": target_date, "cost": cost, "streak": calc_streak(valid, today)}

    async def freeze(
        self, session: AsyncSession, challenge_id: int, user_id: str, target_date: str
    ) -> dict[str, object]:
        challenge = await self._get_owned_challenge(session, challenge_id, user_id)
        today = today_str()
        if target_date < today:
            raise ValueError("只能冻结今天或未来的日期")
        if target_date < challenge.start_date or target_date > challenge.end_date:
            raise ValueError("只能冻结挑战期间内的日期")
        existing = await self._action_repo.get_by_date(
            session, challenge_id, ACTION_FREEZE, target_date
        )
        if existing is not None:
            valid = await self._valid_dates(session, challenge_id)
            return {"date": target_date, "cost": 0, "streak": calc_streak(valid, today)}

        week_dates = week_dates_of()
        used = await self._action_repo.count_user_actions_in_dates(
            session, user_id, ACTION_FREEZE, week_dates
        )
        cost = 0
        if used >= FREE_FREEZE_PER_WEEK:
            ok = await self._points.spend(session, user_id, FREEZE_COST, ACTION_FREEZE, str(challenge_id))
            if not ok:
                raise ValueError(f"免费冻结卡已用完，积分不足{FREEZE_COST}分")
            cost = FREEZE_COST

        await self._action_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "action": ACTION_FREEZE,
            "action_date": target_date,
            "cost": cost,
        })
        valid = await self._valid_dates(session, challenge_id)
        return {"date": target_date, "cost": cost, "streak": calc_streak(valid, today)}

    async def repair(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_owned_challenge(session, challenge_id, user_id)
        today = today_str()
        yesterday = shift_date(today, -1)
        valid = await self._valid_dates(session, challenge_id)
        if yesterday in valid:
            raise ValueError("昨天没有断签，无需修复")
        if yesterday < challenge.start_date or yesterday > challenge.end_date:
            raise ValueError("断签日期不在挑战期间内")
        if streak_before(valid, yesterday) <= 0:
            raise ValueError("断签时间过长，无法修复，请用补签卡逐日补齐")

        month_prefix = month_prefix_of()
        used = await self._action_repo.count_challenge_actions_in_month(
            session, challenge_id, ACTION_REPAIR, month_prefix
        )
        if used >= REPAIR_LIMIT_PER_MONTH:
            raise ValueError("本月修复机会已用完")

        await self._action_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "action": ACTION_REPAIR,
            "action_date": yesterday,
            "cost": 0,
        })
        try:
            message = await self._ai.generate_repair_message(challenge.title, 1)
        except Exception as e:
            logger.warning("repair message fallback: %s", e)
            message = "断签一天不代表失败，只是生活打了个岔。今天完成一个小行动，把节奏接回来。"
        valid.add(yesterday)
        return {"ok": True, "message": message, "streak": calc_streak(valid, today)}

    async def get_mercy_status(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_owned_challenge(session, challenge_id, user_id)
        today = today_str()
        month_prefix = month_prefix_of()
        mend_used = await self._action_repo.count_user_actions_in_month(
            session, user_id, ACTION_MEND, month_prefix
        )
        freeze_used = await self._action_repo.count_user_actions_in_dates(
            session, user_id, ACTION_FREEZE, week_dates_of()
        )
        repair_used = await self._action_repo.count_challenge_actions_in_month(
            session, challenge_id, ACTION_REPAIR, month_prefix
        )
        valid = await self._valid_dates(session, challenge_id)
        yesterday = shift_date(today, -1)
        repair_available = (
            yesterday not in valid
            and challenge.start_date <= yesterday <= challenge.end_date
            and streak_before(valid, yesterday) > 0
            and repair_used < REPAIR_LIMIT_PER_MONTH
        )
        missed = list_missed_dates(challenge.start_date, challenge.end_date, valid, today)
        return {
            "mend_left_this_month": max(0, FREE_MEND_PER_MONTH - mend_used),
            "freeze_left_this_week": max(0, FREE_FREEZE_PER_WEEK - freeze_used),
            "repair_available": repair_available,
            "missed_dates": missed,
            "streak": calc_streak(valid, today),
        }
