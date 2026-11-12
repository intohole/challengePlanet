from __future__ import annotations

import json

from nexus import parse_json_column
from nexus.logging import get_logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import AdaptiveSuggestion
from app.repositories.adaptive_repository import AdaptiveRepository
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.goal_rule_service import is_ladder, ladder_cap, restart_anchor_of
from app.services.plan_parser import parse_ai_plan
from app.services.streak_service import day_number_of, today_str

logger = get_logger("challengePlanet.adaptive")

RESTART_GAP_DAYS = 7
RESTART_WINDOW_DAYS = 3


def fallback_light_task(task: dict[str, object], day: int, mode: str = "lighten") -> dict[str, object]:
    base_title = str(task.get("title", "") or "今日任务")
    base_desc = str(task.get("description", "") or "")
    if mode == "micro":
        return {
            "day": day,
            "title": base_title,
            "description": f"今天只做5分钟最小一步：{base_desc[:30] or base_title}",
            "tip": "微行动也算数，完成比完美重要",
        }
    return {
        "day": day,
        "title": base_title,
        "description": f"轻松版：{base_desc[:40] or base_title}（做到一半就算赢）",
        "tip": "状态不好时，减负是为了走得更远",
    }


class AdaptiveService:
    def __init__(self) -> None:
        self._repo = AdaptiveRepository()
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()

    async def get_pending(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> AdaptiveSuggestion | None:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        suggestion = await self._repo.get_pending(session, challenge_id)
        if suggestion is None:
            return None
        current_day = day_number_of(challenge.start_date, today_str())
        if suggestion.kind == "restart":
            if current_day > int(suggestion.target_day or 0) + RESTART_WINDOW_DAYS:
                await self._repo.update_status(session, suggestion, "expired")
                return None
            return suggestion
        if suggestion.target_day <= current_day or suggestion.target_day > challenge.duration_days:
            await self._repo.update_status(session, suggestion, "expired")
            return None
        return suggestion

    async def respond(
        self, session: AsyncSession, suggestion_id: int, user_id: str, accept: bool
    ) -> dict[str, object]:
        suggestion = await self._repo.get_by_id(session, suggestion_id)
        if suggestion is None or suggestion.user_id != user_id or suggestion.status != "pending":
            raise ValueError("建议不存在或已处理")
        if not accept:
            await self._repo.update_status(session, suggestion, "rejected")
            return {"ok": True, "applied": False}
        challenge = await self._challenge_repo.get_by_id(session, suggestion.challenge_id)
        if challenge is None:
            raise ValueError("挑战不存在")
        if suggestion.kind == "restart":
            task = parse_json_column(suggestion.task_json, {})
            cap = float(task.get("restart_cap") or 0)
            if cap <= 0:
                raise ValueError("重启数据无效")
            challenge.ladder_restart = json.dumps(
                {"date": today_str(), "cap": cap}, ensure_ascii=False,
            )
            await session.flush()
            await self._repo.update_status(session, suggestion, "accepted")
            logger.info(
                "restart anchored: challenge=%s cap=%s date=%s",
                challenge.id, cap, today_str(),
            )
            return {"ok": True, "applied": True}
        plan = parse_ai_plan(challenge.ai_plan)
        task = parse_json_column(suggestion.task_json, {})
        if not task:
            raise ValueError("建议的任务数据无效")
        idx = suggestion.target_day - 1
        if 0 <= idx < len(plan):
            task["day"] = suggestion.target_day
            plan[idx] = task
            challenge.ai_plan = json.dumps(plan, ensure_ascii=False)
            await session.flush()
        await self._repo.update_status(session, suggestion, "accepted")
        return {"ok": True, "applied": True, "task": task}

    async def evaluate_restart_on_return(
        self, session: AsyncSession, challenge: object, gap_days: int,
    ) -> AdaptiveSuggestion | None:
        """长缺席回归的重启建议（r27，纯确定性，零 LLM）。

        判定：cap 阶梯+decrease+缺席≥RESTART_GAP_DAYS+未重锚+缺口前最后有效日的
        当日总量（clamp ≤ladder_start）> 当前日历 cap。幂等：pending 在场跳过，
        同一回归日已答复（accepted/rejected）不再问——尊重用户选择。
        """
        if str(getattr(challenge, "status", "")) != "active":
            return None
        if not is_ladder(challenge) or str(getattr(challenge, "direction", "")) != "decrease":
            return None
        if gap_days < RESTART_GAP_DAYS or restart_anchor_of(challenge) is not None:
            return None
        start = str(getattr(challenge, "start_date", "") or "")
        if not start:
            return None
        today = today_str()
        current_day = day_number_of(start, today)
        current_cap = ladder_cap(challenge, current_day)
        restart_cap = await self._last_valid_day_total(session, int(challenge.id))
        if restart_cap is None:
            return None
        restart_cap = min(restart_cap, float(getattr(challenge, "ladder_start", 0) or restart_cap))
        if restart_cap <= current_cap:
            return None
        existing = await self._repo.latest_by_kind(session, int(challenge.id), "restart")
        if existing is not None and (
            existing.status == "pending" or int(existing.target_day or 0) == current_day
        ):
            return None
        unit = str(getattr(challenge, "unit", "") or "")
        reason = (
            f"离开 {gap_days} 天，阶梯按日历走到了每天 {current_cap:g} {unit}——"
            f"对刚回来的你来说太陡了。上次你守在 {restart_cap:g} {unit}。"
            f"从 {restart_cap:g} {unit} 重新出发，走过的一天都算数。"
        )
        task_json = {
            "restart_cap": restart_cap,
            "current_cap": current_cap,
            "gap_days": gap_days,
            "unit": unit,
            "title": str(getattr(challenge, "title", "") or ""),
        }
        try:
            suggestion = await self._repo.create(session, {
                "challenge_id": int(challenge.id),
                "user_id": str(challenge.user_id),
                "kind": "restart",
                "reason": reason,
                "task_json": json.dumps(task_json, ensure_ascii=False),
                "target_day": current_day,
                "status": "pending",
            })
        except IntegrityError:
            await session.rollback()
            return None
        logger.info(
            "restart suggestion created: challenge=%s cap=%s->%s gap=%s",
            challenge.id, current_cap, restart_cap, gap_days,
        )
        return suggestion

    async def _last_valid_day_total(self, session: AsyncSession, challenge_id: int) -> float | None:
        """缺口前最后一次「真实记录且守住」的当日总量（补齐式 valid 的 max 恒是
        昨天——cap 口径没记录=守住，必须与真实记录日求交）。"""
        from app.services.mercy_service import load_valid_dates

        rows = await self._checkin_repo.get_by_challenge(session, challenge_id)
        recorded = {str(r.date) for r in rows}
        if not recorded:
            return None
        valid = await load_valid_dates(session, challenge_id)
        real = recorded & valid
        if not real:
            return None
        last_day = max(real)
        total = await self._checkin_repo.sum_value_by_date(session, challenge_id, last_day)
        if total is None or total <= 0:
            return None
        return float(total)
