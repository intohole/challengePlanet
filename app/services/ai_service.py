from __future__ import annotations

import json
import time
from collections.abc import AsyncGenerator

from nexus import get_llm_service, parse_llm_json
from nexus.logging import get_logger

from app.config import settings

logger = get_logger("challengePlanet.ai")


class AIService:
    async def generate_challenge_plan(
        self, title: str, description: str, category: str, duration: int
    ) -> dict[str, object]:
        system = (
            "你是一个专业的习惯养成教练。根据用户的挑战目标，生成详细的每日计划。"
            "输出JSON格式：{\"plan\": [{\"day\": 1, \"title\": \"任务标题\", \"description\": \"具体任务\", \"tip\": \"小贴士\"}], \"suggestions\": [\"建议1\", \"建议2\", \"建议3\"]}"
            "每天的任务应该循序渐进，前3天是适应期，中间是巩固期，最后是维持期。"
            f"共{duration}天。每天任务不要太多，1-2个具体可执行的微任务。"
        )
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"

        llm = get_llm_service()
        t0 = time.time()
        raw = await llm.ask(
            user_msg,
            system=system,
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=120.0,
        )
        elapsed = time.time() - t0
        logger.info("Challenge plan generated in %.1fs, len=%d", elapsed, len(raw))
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            logger.error("Plan parse failed, generating fallback")
            parsed = {
                "plan": [
                    {"day": i + 1, "title": f"第{i+1}天", "description": f"坚持{title}", "tip": "保持动力！"}
                    for i in range(duration)
                ],
                "suggestions": ["每天进步一点点", "记录你的感受", "找到你的节奏"],
            }
        return parsed

    async def generate_challenge_plan_stream(
        self, title: str, description: str, category: str, duration: int
    ) -> AsyncGenerator[str, None]:
        yield f'data: {{"step":"thinking","message":"AI正在分析你的挑战目标..."}}\n\n'
        yield f'data: {{"step":"generating","message":"正在生成{duration}天详细计划..."}}\n\n'
        plan = await self.generate_challenge_plan(title, description, category, duration)
        result = {"step": "done", "plan": plan.get("plan", []), "suggestions": plan.get("suggestions", [])}
        yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

    async def generate_daily_feedback(
        self, challenge_title: str, day_number: int, total_days: int,
        mood: str, reflection: str,
    ) -> str:
        system = (
            "你是一个温暖、幽默的打卡教练。根据用户的打卡数据，给出简短(2-3句话)的个性化反馈。"
            "要鼓励用户，但不要空洞。根据心情和心得给出有针对性的建议。"
        )
        phase = "适应期" if day_number <= 3 else ("巩固期" if day_number <= total_days * 0.6 else "维持期")
        user_msg = (
            f"挑战：{challenge_title}\n第{day_number}/{total_days}天 ({phase})\n"
            f"心情：{mood}\n心得：{reflection or '无'}"
        )

        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=system,
            temperature=settings.FEEDBACK_TEMPERATURE,
            max_tokens=256,
            timeout=30.0,
        )
        return raw.strip()

    async def generate_insight(
        self, challenge_title: str, checkins: list[dict[str, object]], total_days: int,
    ) -> str:
        system = (
            "你是一个数据分析型习惯教练。根据用户的打卡历史，生成一段洞察(3-5句话)。"
            "分析用户的坚持模式、心情趋势、潜在风险，给出具体建议。"
            "输出纯文本，不要JSON。"
        )
        checkin_summary = "\n".join(
            f"第{c.get('day_number', 0)}天 心情:{c.get('mood', 'unknown')} 心得:{str(c.get('reflection', ''))[:50]}"
            for c in checkins[-7:]
        )
        user_msg = f"挑战：{challenge_title} ({total_days}天)\n最近打卡：\n{checkin_summary}"

        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=system,
            temperature=0.6,
            max_tokens=512,
            timeout=30.0,
        )
        return raw.strip()
