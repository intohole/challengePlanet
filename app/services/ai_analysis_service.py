from __future__ import annotations

import json

from nexus import get_llm_service, parse_llm_json
from nexus.logging import get_logger

from app.config import settings
from app.services.prompts import (
    ADJUST_TASKS_SYSTEM,
    DECOMPOSE_SYSTEM,
    DIAGNOSIS_SYSTEM,
    INSIGHT_SYSTEM,
    WEEKLY_SYSTEM,
)

logger = get_logger("challengePlanet.ai_analysis")


class AIAnalysisService:
    async def generate_weekly_report(
        self, challenge_title: str, checkins: list[dict[str, object]], total_days: int,
    ) -> str:
        checkin_summary = "\n".join(
            f"第{c.get('day_number', 0)}天 心情:{c.get('mood', 'unknown')} "
            f"值:{c.get('value', 0)} 心得:{str(c.get('reflection', ''))[:50]}"
            for c in checkins[-7:]
        )
        done_rate = len(checkins) / total_days * 100 if total_days > 0 else 0
        user_msg = (
            f"挑战：{challenge_title} (共{total_days}天，累计记录率{done_rate:.0f}%)\n"
            f"最近打卡：\n{checkin_summary or '暂无记录'}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=WEEKLY_SYSTEM,
            temperature=0.6, max_tokens=512, timeout=30.0,
        )
        return raw.strip()

    async def diagnose_break(
        self, challenge_title: str, missed_count: int, total_days: int,
        done_days: int, recent_summary: str,
    ) -> dict[str, object] | None:
        user_msg = (
            f"挑战：{challenge_title}（共{total_days}天，已记录{done_days}天，本次中断{missed_count}天）\n"
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

    async def suggest_decompose(
        self, title: str, description: str, category: str,
        target_value: float, unit: str, direction: str, goal_type: str,
        duration_days: int,
    ) -> dict[str, object]:
        user_msg = (
            f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n"
            f"每日目标：{target_value}{unit}\n方向：{direction}\n目标类型：{goal_type}\n"
            f"挑战天数：{duration_days}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=DECOMPOSE_SYSTEM,
            temperature=0.3, max_tokens=512, timeout=30.0,
        )
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            return {
                "decompose_mode": "none", "slot_hours": 1,
                "slot_target_value": 0.0, "sub_goals": [],
                "rationale": "暂不拆解，先观察用户打卡模式",
            }
        if not isinstance(parsed.get("sub_goals"), list):
            parsed["sub_goals"] = []
        parsed["decompose_mode"] = parsed.get("decompose_mode", "none")
        parsed["slot_hours"] = int(parsed.get("slot_hours", 1))
        parsed["slot_target_value"] = float(parsed.get("slot_target_value", 0.0))
        parsed["rationale"] = str(parsed.get("rationale", ""))
        parsed["sub_goals"] = parsed["sub_goals"][:4]
        return parsed

    async def generate_deep_insight(
        self, challenge_title: str, direction: str, unit: str,
        checkins_data: list[dict[str, object]],
    ) -> dict[str, object] | None:
        if len(checkins_data) < 3:
            return None
        summary_lines: list[str] = []
        for c in checkins_data[-30:]:
            ts = c.get("timestamp", "")
            hour_str = ""
            if ts:
                try:
                    hour_str = str(int(ts[11:13])) + ":00"
                except (ValueError, IndexError):
                    hour_str = "?"
            summary_lines.append(
                f"{ts[:10]} {hour_str} 值:{c.get('value', 0)}{unit} "
                f"心情:{c.get('mood', 'unknown')} 情境:{c.get('context_tag', '')}"
            )
        user_msg = (
            f"挑战：{challenge_title}\n方向：{direction}{'(越少越好)' if direction == 'decrease' else '(越多越好)'}\n"
            f"最近30条打卡：\n" + "\n".join(summary_lines)
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg, system=INSIGHT_SYSTEM,
            temperature=0.4, max_tokens=384, timeout=30.0,
        )
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            return None
        valid_types = {"pattern", "risk", "progress"}
        if parsed.get("insight_type") not in valid_types:
            parsed["insight_type"] = "pattern"
        try:
            parsed["confidence"] = float(parsed.get("confidence", 0.5))
        except (TypeError, ValueError):
            parsed["confidence"] = 0.5
        return parsed
