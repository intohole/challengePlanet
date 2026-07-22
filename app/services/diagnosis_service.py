from __future__ import annotations

import json

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.adaptive_service import fallback_light_task
from app.services.ai_service import AIService
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import day_number_of, list_missed_dates, today_str

logger = get_logger("challengePlanet.diagnosis")

CAUSE_LABELS = {
    "task_hard": "任务偏重",
    "no_time": "时间不足",
    "motivation_decay": "动力衰减",
    "external": "外部干扰",
}
ACTION_LABELS = {"lighten3": "未来3天降难度版", "micro": "未来7天微习惯版", "keep": "保持原计划"}

_TASK_HARD_KW = ("累", "太多", "做不完", "太难", "吃不消", "坚持不住")
_NO_TIME_KW = ("加班", "出差", "没时间", "太忙", "来不及", "开会")
_EXTERNAL_KW = ("生病", "感冒", "发烧", "旅行", "回老家", "突发", "家里有事")
_RULE_ACTION = {"task_hard": "lighten3", "no_time": "micro", "motivation_decay": "micro", "external": "keep"}


class DiagnosisService:
    def __init__(self) -> None:
        self._challenge_repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._insight_repo = InsightRepository()
        self._ai = AIService()

    async def _get_owned(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> Challenge:
        challenge = await self._challenge_repo.get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            raise ValueError("挑战不存在")
        return challenge

    def _rule_cause(self, checkins: list[CheckIn]) -> str:
        recent = checkins[-5:]
        text = " ".join(c.reflection or "" for c in recent)
        if any(k in text for k in _EXTERNAL_KW):
            return "external"
        if any(k in text for k in _TASK_HARD_KW):
            return "task_hard"
        if any(k in text for k in _NO_TIME_KW):
            return "no_time"
        hours = [c.created_at.hour for c in recent if c.created_at is not None]
        if len(hours) >= 3 and hours == sorted(hours) and hours[-1] - hours[0] >= 3:
            return "no_time"
        moods = [c.mood for c in recent if c.mood]
        if moods.count("bad") >= 2:
            return "motivation_decay"
        lens = [len(c.reflection or "") for c in recent]
        if len(lens) >= 3 and lens[0] > 0 and lens[-1] <= lens[0] / 2:
            return "motivation_decay"
        return "motivation_decay"

    def _rule_narrative(self, cause: str, done_days: int, total_days: int) -> str:
        pct = round(done_days / total_days * 100) if total_days else 0
        base = (
            f"偶尔断签并不会毁掉习惯养成，研究证实真正关键的是尽快恢复节奏。"
            f"你已经完成 {done_days}/{total_days} 天（{pct}%），这是实打实的进度，不会清零。"
        )
        tail = {
            "task_hard": "从记录看任务量可能偏重，适当降档反而能走得更远。",
            "no_time": "最近时间似乎被挤压了，换成每天5分钟的微行动更容易守住节奏。",
            "motivation_decay": "动力波动人人都会遇到，用最小行动重启，动机往往会在行动中回来。",
            "external": "生活难免有突发状况，欢迎回来，从今天的一个小行动接上就好。",
        }
        return base + tail.get(cause, "")

    async def diagnose(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object]:
        challenge = await self._get_owned(session, challenge_id, user_id)
        valid = await load_valid_dates(session, challenge_id)
        missed = list_missed_dates(challenge.start_date, challenge.end_date, valid, today_str())
        if not missed:
            raise ValueError("当前没有断签记录，不需要诊断")
        checkins = await self._checkin_repo.get_by_challenge(session, challenge_id)
        done_days = len(checkins)
        recent_summary = "\n".join(
            f"第{c.day_number}天 {c.date} {c.created_at.hour if c.created_at else '?'}点打卡 "
            f"心情:{c.mood or '未记录'} 心得:{(c.reflection or '')[:40]}"
            for c in checkins[-7:]
        )
        ai_result: dict[str, object] | None = None
        try:
            ai_result = await self._ai.diagnose_break(
                challenge.title, len(missed), challenge.duration_days, done_days, recent_summary
            )
        except Exception as e:
            logger.warning("diagnose llm failed, use rule: %s", e)
        if ai_result:
            cause = str(ai_result["cause"])
            action = str(ai_result.get("suggestion_action") or _RULE_ACTION[cause])
            narrative = str(ai_result.get("narrative") or "") or self._rule_narrative(cause, done_days, challenge.duration_days)
            suggestion_text = str(ai_result.get("suggestion_text") or "") or ACTION_LABELS[action]
        else:
            cause = self._rule_cause(checkins)
            action = _RULE_ACTION[cause]
            narrative = self._rule_narrative(cause, done_days, challenge.duration_days)
            suggestion_text = ACTION_LABELS[action]
        report: dict[str, object] = {
            "cause": cause,
            "cause_label": CAUSE_LABELS[cause],
            "narrative": narrative,
            "suggestion_action": action,
            "suggestion_text": suggestion_text,
            "missed_count": len(missed),
            "done_days": done_days,
            "total_days": challenge.duration_days,
        }
        insight = await self._insight_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "insight_type": "diagnosis",
            "content": json.dumps(report, ensure_ascii=False),
        })
        report["report_id"] = insight.id
        return report

    async def get_latest(
        self, session: AsyncSession, challenge_id: int, user_id: str
    ) -> dict[str, object] | None:
        await self._get_owned(session, challenge_id, user_id)
        insights = await self._insight_repo.get_by_challenge(session, challenge_id, limit=10)
        for insight in insights:
            if insight.insight_type != "diagnosis":
                continue
            try:
                report = json.loads(insight.content)
            except (json.JSONDecodeError, TypeError):
                return None
            if isinstance(report, dict):
                report["report_id"] = insight.id
                return report
        return None

    async def apply(
        self, session: AsyncSession, challenge_id: int, user_id: str, action: str
    ) -> dict[str, object]:
        challenge = await self._get_owned(session, challenge_id, user_id)
        if action not in ("lighten3", "micro", "keep"):
            raise ValueError("未知的应用方案")
        if action == "keep":
            return {"ok": True, "message": "好的，保持原计划。今天的一个小行动，就是最好的重启。"}
        try:
            plan = json.loads(challenge.ai_plan) if challenge.ai_plan else []
        except json.JSONDecodeError:
            plan = []
        if not plan:
            raise ValueError("暂无可调整的计划")
        today = today_str()
        current_day = day_number_of(challenge.start_date, today)
        today_checked = await self._checkin_repo.get_by_date(session, challenge_id, today) is not None
        start_day = current_day + 1 if today_checked else current_day
        count = 3 if action == "lighten3" else 7
        mode = "lighten" if action == "lighten3" else "micro"
        targets = [
            (d, plan[d - 1])
            for d in range(max(1, start_day), min(current_day + count, challenge.duration_days) + 1)
            if 0 <= d - 1 < len(plan)
        ]
        if not targets:
            raise ValueError("没有可调整的未来任务")
        adjusted: list[dict[str, object]] | None = None
        try:
            adjusted = await self._ai.generate_adjusted_tasks(
                challenge.title, [t for _, t in targets], mode
            )
        except Exception as e:
            logger.warning("apply adjust llm failed, use fallback: %s", e)
        adjusted_by_day: dict[int, dict[str, object]] = {}
        for t in adjusted or []:
            try:
                adjusted_by_day[int(t.get("day", 0))] = t
            except (TypeError, ValueError):
                continue
        for day, original in targets:
            new_task = adjusted_by_day.get(day) or fallback_light_task(original, day, mode)
            new_task["day"] = day
            plan[day - 1] = new_task
        challenge.ai_plan = json.dumps(plan, ensure_ascii=False)
        await session.flush()
        return {
            "ok": True,
            "message": f"已应用「{ACTION_LABELS[action]}」，共调整 {len(targets)} 天，立即生效",
            "adjusted_days": len(targets),
        }
