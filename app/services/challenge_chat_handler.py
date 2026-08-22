"""挑战星球统一聊天处理器 — 接入 nexus.chat 引擎试点。

承载挑战星球领域差异: 挑战进度/连续天数/风险检测/阶梯玩法进度。
"""

from __future__ import annotations

from typing import AsyncIterator

from nexus import get_llm_service
from nexus.chat.context import ChatContext
from nexus.chat.handler import BaseChatHandler

from app.db.database import async_session
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.services.companion_service import _detect_phase, assess_risk
from app.services.goal_rule_service import is_ladder, ladder_progress_pct
from app.services.streak_service import calc_streak, day_number_of, today_str


class ChallengeChatHandler(BaseChatHandler):
    default_title = "挑战伴学"
    capabilities = {"chat", "stream", "meta"}

    async def build_context(self, context: ChatContext) -> None:
        meta = context.meta
        challenge_id = meta.get("challenge_id")
        if challenge_id is not None:
            challenge_id = int(challenge_id)
        state: dict = {"challenge_id": challenge_id}
        if not challenge_id:
            state["error"] = "no_challenge"
            context.domain_state = state
            return
        state.update(await _load_challenge_state(str(context.conversation.user_id), challenge_id))
        context.domain_state = state
        if state.get("error"):
            return
        context.context_parts = _build_parts(state)

    async def stream_reply(
        self, context: ChatContext, messages: list[dict[str, str]]
    ) -> AsyncIterator[str | dict]:
        state = context.domain_state
        if state.get("error") == "no_challenge":
            yield "先选一个正在坚持的挑战，我就能陪你一起稳住节奏～"
            yield {"type": "meta", **self.stream_meta(context)}
            return
        if state.get("error") == "not_found":
            yield "这个挑战不存在或不属于你哦～"
            yield {"type": "meta", **self.stream_meta(context)}
            return
        system = _build_system_prompt(state)
        async for chunk in get_llm_service().stream_ask(
            context.user_message, system=system,
            temperature=0.8, max_tokens=160, task_type="assistant",
        ):
            yield chunk
        yield {"type": "meta", **self.stream_meta(context)}

    def stream_meta(self, context: ChatContext) -> dict:
        state = context.domain_state
        risk = state.get("risk") or {}
        return {
            "challenge_id": state.get("challenge_id"),
            "completed_days": state.get("completed_days", 0),
            "streak": state.get("streak", 0),
            "phase": state.get("phase", ""),
            "risk_level": risk.get("level", "low"),
            "risk_score": risk.get("score", 0),
            "ladder_progress_pct": state.get("ladder_progress_pct"),
        }

    async def on_reply_complete(
        self, context: ChatContext, user_message: str, reply: str
    ) -> dict | None:
        state = context.domain_state
        risk = state.get("risk") or {}
        return {
            "challenge_id": state.get("challenge_id"),
            "completed_days": state.get("completed_days", 0),
            "streak": state.get("streak", 0),
            "phase": state.get("phase", ""),
            "risk_level": risk.get("level", "low"),
            "risk_score": risk.get("score", 0),
            "ladder_progress_pct": state.get("ladder_progress_pct"),
        }


async def _load_challenge_state(user_id: str, challenge_id: int) -> dict:
    async with async_session() as session:
        challenge = await ChallengeRepository().get_by_id(session, challenge_id)
        if challenge is None or challenge.user_id != user_id:
            return {"error": "not_found"}
        checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
        valid = {c.date for c in checkins}
        today = today_str()
        streak = calc_streak(valid, today)
        phase = _detect_phase(len(checkins))
        risk = assess_risk(checkins, streak, today)
        day_number = day_number_of(challenge.start_date, today) if challenge.start_date else 1
        ladder_pct = ladder_progress_pct(challenge, day_number) if is_ladder(challenge) else None
        return {
            "challenge": challenge,
            "checkins": checkins,
            "completed_days": len(checkins),
            "streak": streak,
            "phase": phase,
            "risk": risk,
            "day_number": day_number,
            "ladder_progress_pct": ladder_pct,
        }


def _build_parts(state: dict) -> list[str]:
    challenge = state["challenge"]
    risk = state["risk"]
    direction = "越少越好" if challenge.direction == "decrease" else "越多越好"
    parts = [
        f"## 挑战：{challenge.title}",
        f"目标：每天{challenge.target_value}{challenge.unit}（{direction}）",
        f"进度：已完成{state['completed_days']}天 / 共{challenge.duration_days}天，当前连续{state['streak']}天",
        f"阶段：{state['phase']}",
    ]
    if state.get("ladder_progress_pct") is not None:
        parts.append(f"阶梯进度：{state['ladder_progress_pct']:.0f}%")
    if risk.get("reasons"):
        parts.append("风险信号：" + "；".join(str(r) for r in risk["reasons"]))
    if risk.get("micro_action"):
        parts.append(f"微行动建议：{risk['micro_action']}")
    return parts


def _build_system_prompt(state: dict) -> str:
    challenge = state["challenge"]
    risk = state["risk"]
    direction = "越少越好" if challenge.direction == "decrease" else "越多越好"
    reasons = "；".join(str(r) for r in risk.get("reasons", [])) or "目前节奏稳定"
    return (
        "你是「星轨挑战」的AI伴学伙伴。用户在坚持一个习惯挑战，你根据挑战进度和风险信号，"
        "给出共情陪伴和可执行的建议。\n"
        f"## 挑战信息\n标题：{challenge.title}\n"
        f"目标：每天{challenge.target_value}{challenge.unit}（{direction}）\n"
        f"玩法：{challenge.goal_rule}\n"
        f"进度：已完成{state['completed_days']}天 / 共{challenge.duration_days}天，当前连续{state['streak']}天\n"
        f"阶段：{state['phase']}\n"
        f"## 风险信号\n{reasons}\n"
        "## 语言规范\n"
        "1. 只说提醒与陪伴，绝不评判、不指责、不下命令\n"
        "2. 禁用'破戒/失败/断签/应该'，改用'中断/信号/我注意到/要不要试试'\n"
        "3. 结尾给1个5分钟内可执行的轻量微行动\n"
        "4. 不超过100字"
    )


challenge_chat_handler = ChallengeChatHandler()
