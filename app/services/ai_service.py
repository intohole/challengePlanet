from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from nexus import get_llm_service, parse_llm_json
from nexus.logging import get_logger

from app.config import settings
from app.services.prompts import (
    ADJUST_TASKS_SYSTEM,
    DECLARATION_SYSTEM,
    DIAGNOSIS_SYSTEM,
    FEEDBACK_SYSTEM,
    PARSE_SYSTEM,
    PLAN_SYSTEM,
    QUOTE_SYSTEM,
    REPAIR_SYSTEM,
    WEEKLY_SYSTEM,
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

    async def parse_challenge_input(self, raw_input: str) -> dict[str, object]:
        llm = get_llm_service()
        raw = await llm.ask(
            raw_input,
            system=PARSE_SYSTEM,
            temperature=0.3,
            max_tokens=256,
            timeout=15.0,
        )
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            parsed = {
                "title": raw_input[:10],
                "category": "other",
                "duration_days": 30,
                "description": raw_input,
            }
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
            user_msg,
            system=system,
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=120.0,
        )
        return self.parse_plan_text(raw, title, duration)

    async def generate_challenge_plan_stream(
        self, title: str, description: str, category: str, duration: int,
        scene_template: str = "",
    ) -> AsyncGenerator[str, None]:
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"
        system = self._build_plan_system(scene_template, duration)
        llm = get_llm_service()
        async for token in llm.stream_ask(
            user_msg,
            system=system,
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
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
    ) -> str:
        phase = "适应期" if day_number <= 3 else ("巩固期" if day_number <= total_days * 0.6 else "维持期")
        memory_part = f"\n用户过往记忆：{memory_context}" if memory_context else ""
        user_msg = (
            f"挑战：{challenge_title}\n第{day_number}/{total_days}天 ({phase})\n"
            f"心情：{mood or '未记录'}\n心得：{reflection or '无'}{memory_part}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=FEEDBACK_SYSTEM,
            temperature=settings.FEEDBACK_TEMPERATURE,
            max_tokens=256,
            timeout=30.0,
        )
        return raw.strip()

    async def generate_weekly_report(
        self, challenge_title: str, checkins: list[dict[str, object]], total_days: int,
    ) -> str:
        checkin_summary = "\n".join(
            f"第{c.get('day_number', 0)}天 心情:{c.get('mood', 'unknown')} 心得:{str(c.get('reflection', ''))[:50]}"
            for c in checkins[-7:]
        )
        done_rate = len(checkins) / total_days * 100 if total_days > 0 else 0
        user_msg = (
            f"挑战：{challenge_title} (共{total_days}天，累计完成率{done_rate:.0f}%)\n"
            f"最近打卡：\n{checkin_summary or '暂无记录'}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=WEEKLY_SYSTEM,
            temperature=0.6,
            max_tokens=512,
            timeout=30.0,
        )
        return raw.strip()

    async def generate_repair_message(self, challenge_title: str, missed_days: int) -> str:
        user_msg = f"挑战：{challenge_title}\n断签天数：{missed_days}天"
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=REPAIR_SYSTEM, temperature=0.7, max_tokens=128, timeout=20.0)
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
        user_msg = (
            f"挑战：{challenge_title}（共{total_days}天，已完成{done_days}天，本次断签{missed_count}天）\n"
            f"最近打卡记录：\n{recent_summary or '暂无'}"
        )
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=DIAGNOSIS_SYSTEM, temperature=0.4, max_tokens=384, timeout=30.0)
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            return None
        if parsed.get("cause") not in ("task_hard", "no_time", "motivation_decay", "external"):
            return None
        if parsed.get("suggestion_action") not in ("lighten3", "micro", "keep"):
            parsed["suggestion_action"] = "lighten3"
        return parsed

    async def generate_adjusted_tasks(
        self, challenge_title: str, tasks: list[dict[str, object]], mode: str,
    ) -> list[dict[str, object]] | None:
        user_msg = f"挑战：{challenge_title}\n模式：{mode}\n原任务：{json.dumps(tasks, ensure_ascii=False)}"
        llm = get_llm_service()
        raw = await llm.ask(user_msg, system=ADJUST_TASKS_SYSTEM, temperature=0.5, max_tokens=2048, timeout=60.0)
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed or not isinstance(parsed.get("tasks"), list):
            return None
        return [t for t in parsed["tasks"] if isinstance(t, dict) and t.get("title")]
