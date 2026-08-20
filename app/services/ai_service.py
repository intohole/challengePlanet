from __future__ import annotations

from collections.abc import AsyncGenerator

from nexus import get_llm_service, parse_llm_json
from nexus.logging import get_logger

from app.config import settings
from app.services.ai_analysis_service import AIAnalysisService
from app.services.prompts import (
    COMPANION_SYSTEM,
    DECLARATION_SYSTEM,
    FEEDBACK_SYSTEM,
    PARSE_SYSTEM,
    PLAN_SYSTEM,
    QUOTE_SYSTEM,
    REPAIR_SYSTEM,
    get_mood_aware_prefix,
)
from app.services.scene_service import SceneService

logger = get_logger("challengePlanet.ai")


def _fit_plan_length(plan: list[dict[str, object]], title: str, duration: int) -> list[dict[str, object]]:
    if duration <= 0:
        duration = len(plan)
    fitted = plan[:duration]
    template = dict(fitted[-1]) if fitted else {}
    while len(fitted) < duration:
        day = len(fitted) + 1
        item = dict(template)
        item["day"] = day
        item["title"] = str(template.get("title") or f"第{day}天")
        item["description"] = str(template.get("description") or f"坚持{title}")
        item["tip"] = str(template.get("tip") or "")
        item.setdefault("task_type", template.get("task_type", "binary"))
        item.setdefault("target_value", template.get("target_value", 0))
        item.setdefault("unit", template.get("unit", ""))
        item.setdefault("difficulty", template.get("difficulty", 1))
        item.setdefault("steps", template.get("steps", []))
        fitted.append(item)
    for idx, item in enumerate(fitted):
        item["day"] = idx + 1
        item.setdefault("task_type", "binary")
        item.setdefault("target_value", 0)
        item.setdefault("unit", "")
        item.setdefault("difficulty", 1)
        item.setdefault("steps", [])
    return fitted


class AIService:
    def __init__(self) -> None:
        self._scenes = SceneService()
        self._analysis = AIAnalysisService()

    async def parse_challenge_input(self, raw_input: str) -> dict[str, object]:
        llm = get_llm_service()
        raw = await llm.ask(raw_input, system=PARSE_SYSTEM, temperature=0.3, max_tokens=256, timeout=30.0, task_type="extract")
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            parsed = {
                "title": raw_input[:10], "category": "other", "duration_days": 30,
                "description": raw_input, "target_value": 1.0, "unit": "次",
                "direction": "increase", "goal_type": "hard",
                "decompose_mode": "none", "slot_hours": 1, "slot_target_value": 0.0,
            }
        parsed.setdefault("target_value", 1.0)
        parsed.setdefault("unit", "次")
        parsed.setdefault("direction", "increase")
        parsed.setdefault("goal_type", "hard")
        parsed.setdefault("decompose_mode", "none")
        parsed.setdefault("slot_hours", 1)
        parsed.setdefault("slot_target_value", 0.0)
        return parsed

    def _build_plan_system(self, scene_template: str, duration: int) -> str:
        base = f"{PLAN_SYSTEM}共{duration}天。"
        if scene_template:
            hint = self._scenes.build_plan_hint(scene_template, duration)
            if hint:
                base += hint
        return base

    async def generate_challenge_plan(
        self, title: str, description: str, category: str, duration: int,
        scene_template: str = "",
    ) -> dict[str, object]:
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"
        system = self._build_plan_system(scene_template, duration)
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=system,
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS, timeout=120.0,
            task_type="extract",
        )
        return self.parse_plan_text(raw, title, duration)

    async def generate_challenge_plan_stream(
        self, title: str, description: str, category: str, duration: int,
        scene_template: str = "", adjust_hint: str = "",
    ) -> AsyncGenerator[str, None]:
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"
        if adjust_hint.strip():
            user_msg += f"\n\n此前已生成过一版计划，现用户提出调整意见，请严格据此重新生成完整计划：{adjust_hint.strip()}"
        system = self._build_plan_system(scene_template, duration)
        llm = get_llm_service()
        async for token in llm.stream_ask(
            user_msg, system=system,
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            task_type="extract",
        ):
            yield token

    def parse_plan_text(self, raw: str, title: str, duration: int) -> dict[str, object]:
        parsed = parse_llm_json(raw)
        if "raw_response" not in parsed and isinstance(parsed.get("plan"), list):
            plan = [dict(d) for d in parsed["plan"] if isinstance(d, dict)]
            if plan:
                parsed["plan"] = _fit_plan_length(plan, title, duration)
                return parsed
        logger.error("Plan parse failed, generating fallback")
        return {
            "plan": [
                {
                    "day": i + 1, "title": f"第{i + 1}天",
                    "description": f"坚持{title}", "tip": "保持动力！",
                    "task_type": "binary", "target_value": 0, "unit": "",
                    "difficulty": 1, "steps": [],
                }
                for i in range(duration)
            ],
            "suggestions": ["每天进步一点点", "记录你的感受", "找到你的节奏"],
        }

    async def generate_daily_feedback(
        self, challenge_title: str, day_number: int, total_days: int,
        mood: str, reflection: str, memory_context: str,
        value: float = 0.0, target: float = 0.0,
        direction: str = "increase", is_soft_exceeded: bool = False,
    ) -> str:
        phase = "适应期" if day_number <= 3 else ("巩固期" if day_number <= total_days * 0.6 else "维持期")
        memory_part = f"\n用户过往记忆：{memory_context}" if memory_context else ""
        soft_exceed_hint = self._build_soft_exceed_hint(value, target, direction, is_soft_exceeded, mood)
        user_msg = (
            f"挑战：{challenge_title}\n第{day_number}/{total_days}天 ({phase})\n"
            f"心情：{mood or '未记录'}\n本次记录值：{value}\n目标值：{target}\n"
            f"方向：{direction}{'(越少越好)' if direction == 'decrease' else '(越多越好)'}\n"
            f"心得：{reflection or '无'}{soft_exceed_hint}{memory_part}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=get_mood_aware_prefix(mood) + FEEDBACK_SYSTEM,
            temperature=settings.FEEDBACK_TEMPERATURE,
            max_tokens=256, timeout=30.0, task_type="assistant",
        )
        return raw.strip()

    def _build_soft_exceed_hint(
        self, value: float, target: float, direction: str, is_soft_exceeded: bool, mood: str = "",
    ) -> str:
        if not is_soft_exceeded:
            return ""
        if mood == "bad":
            return (
                f"\n【场景】用户本次记录{value}，软目标是{target}，心情低落。"
                "绝不使用'这个时段对你来说特别难'，改用'没关系，记录本身就是进步'。"
            )
        if direction == "decrease":
            return (
                f"\n【场景】用户本次记录{value}，软目标是{target}，超出了。"
                "请用'这个时段对你来说特别难'的语气共情，绝不指责。"
            )
        return (
            f"\n【场景】用户本次记录{value}，软目标是{target}，未达成。"
            "请用'慢慢来，我们一起想办法'的语气鼓励。"
        )

    async def generate_weekly_report(
        self, challenge_title: str, checkins: list[dict[str, object]], total_days: int,
    ) -> str:
        return await self._analysis.generate_weekly_report(challenge_title, checkins, total_days)

    async def generate_repair_message(self, challenge_title: str, missed_days: int) -> str:
        user_msg = f"挑战：{challenge_title}\n中断天数：{missed_days}天"
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=REPAIR_SYSTEM, temperature=0.7, max_tokens=128, timeout=20.0, task_type="assistant")
        return raw.strip()

    async def generate_companion_message(
        self, challenge_title: str, streak: int, phase_key: str, reasons: list[str]
    ) -> str:
        reason_text = "；".join(reasons) if reasons else "目前节奏稳定"
        user_msg = (
            f"挑战：{challenge_title}\n当前连续：{streak}天\n阶段：{phase_key}\n"
            f"断签风险信号：{reason_text}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=COMPANION_SYSTEM,
            temperature=0.8, max_tokens=96, timeout=20.0, task_type="assistant",
        )
        return raw.strip()

    async def generate_share_quote(self, challenge_title: str, streak: int) -> str:
        user_msg = f"挑战：{challenge_title}\n已连续坚持：{streak}天"
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=QUOTE_SYSTEM, temperature=0.8, max_tokens=64, timeout=15.0)
        quote = raw.strip().strip('"').strip("'").split("\n")[0].strip()
        return quote[:20] if quote else "坚持，是最好的答案"

    async def generate_declaration(self, challenge_title: str, day_number: int, streak: int) -> str:
        user_msg = f"挑战：{challenge_title}\n今天是第{day_number}天，已连续{streak}天"
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=DECLARATION_SYSTEM, temperature=0.9, max_tokens=48, timeout=12.0)
        text = raw.strip().strip('"').strip("'").split("\n")[0].strip()
        return text[:20]

    async def diagnose_break(
        self, challenge_title: str, missed_count: int, total_days: int,
        done_days: int, recent_summary: str,
    ) -> dict[str, object] | None:
        return await self._analysis.diagnose_break(
            challenge_title, missed_count, total_days, done_days, recent_summary
        )

    async def generate_adjusted_tasks(
        self, challenge_title: str, tasks: list[dict[str, object]], mode: str,
    ) -> list[dict[str, object]] | None:
        return await self._analysis.generate_adjusted_tasks(challenge_title, tasks, mode)

    async def suggest_decompose(
        self, title: str, description: str, category: str,
        target_value: float, unit: str, direction: str, goal_type: str,
        duration_days: int,
    ) -> dict[str, object]:
        return await self._analysis.suggest_decompose(
            title, description, category, target_value, unit, direction, goal_type, duration_days
        )

    async def generate_deep_insight(
        self, challenge_title: str, direction: str, unit: str,
        checkins_data: list[dict[str, object]],
    ) -> dict[str, object] | None:
        return await self._analysis.generate_deep_insight(
            challenge_title, direction, unit, checkins_data
        )
