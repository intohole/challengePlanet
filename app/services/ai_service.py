from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from nexus import get_llm_service, parse_llm_json
from nexus.logging import get_logger

from app.config import settings

logger = get_logger("challengePlanet.ai")

_PARSE_SYSTEM = (
    "你是一个挑战目标解析器。从用户的自然语言描述中提取挑战参数。"
    "输出JSON格式：{\"title\": \"简短标题\", \"category\": \"quit|build|learn|fitness|mind|other\", \"duration_days\": 30, \"description\": \"一句话描述\"}\n"
    "分类规则：quit=戒除坏习惯(戒烟/戒酒/戒糖等), build=培养好习惯(早起/冥想等), "
    "learn=学习技能(读书/编程/语言等), fitness=运动健身(跑步/健身等), mind=心智成长(日记/感恩等), other=其他\n"
    "duration_days: 从描述中提取天数；若用户未明确，优先推荐 21、42 或 66 天"
    "（66天是科学习惯养成周期，21天适合轻量目标，42天适合中等目标）。标题不超过10个字。"
)

_PLAN_SYSTEM = (
    "你是一个专业的习惯养成教练。根据用户的挑战目标，生成详细的每日计划。"
    "只输出严格JSON，不要输出任何其他文字或markdown代码块标记："
    "{\"plan\": [{\"day\": 1, \"title\": \"任务标题\", \"description\": \"具体任务\", \"tip\": \"小贴士\"}], \"suggestions\": [\"建议1\", \"建议2\", \"建议3\"]}\n"
    "每天的任务应该循序渐进，前3天是适应期，中间是巩固期，最后是维持期。"
    "每天任务不要太多，1-2个具体可执行的微任务。"
)

_FEEDBACK_SYSTEM = (
    "你是一个温暖、幽默的打卡教练。根据用户的打卡数据，给出简短(2-3句话)的个性化反馈。"
    "要求：温暖共情，严禁羞辱式或指责式表达；根据心情和心得给出有针对性的回应；"
    "若用户正处于断签高风险期（如连续打卡后进入疲惫期、心情连续低落），给出1条具体可执行的应对建议。"
    "若能感知到用户过往的记忆脉络，自然地呼应，但不要生硬引用。"
)

_WEEKLY_SYSTEM = (
    "你是一个数据分析型习惯教练。根据用户本周打卡记录，生成结构化周报，4-6句纯文本，不要JSON。涵盖："
    "1)本周完成率简评 2)心情趋势观察 3)主要障碍识别 4)下周3条具体可行动建议（用①②③列出）。"
)

_REPAIR_SYSTEM = (
    "你是一个温暖的习惯教练。用户挑战断签了，写2句话：第一句共情（断签很正常，不指责），"
    "第二句给出修复引导（鼓励今天立刻完成一个小行动重启）。严禁羞辱式表达。"
)

_QUOTE_SYSTEM = (
    "你是文案高手。为用户的坚持挑战写一句分享海报金句，不超过20个字，有力量感，"
    "不要emoji，不要引号，直接输出这句话本身。"
)

_DECLARATION_SYSTEM = (
    "你是点燃仪式感的教练。为用户今天的打卡写一句今日宣言，不超过16字，"
    "第一人称、有力量感、不油腻，不要emoji，不要引号，直接输出这句话本身。"
)

_DIAGNOSIS_SYSTEM = (
    "你是习惯养成领域的执行力诊断专家。用户挑战断签了，根据数据推断最可能的断签原因。"
    "只输出严格JSON，不要markdown标记："
    "{\"cause\": \"task_hard|no_time|motivation_decay|external\", "
    "\"narrative\": \"2-3句叙事重塑文案：先共情正常化（偶尔断签不影响习惯养成），再肯定已完成进度，严禁指责\", "
    "\"suggestion_action\": \"lighten3|micro|keep\", "
    "\"suggestion_text\": \"一句话方案说明\"}\n"
    "归因规则：心得提到累/太多/做不完→task_hard；提到加班/出差/没时间，或打卡时间逐日推迟→no_time；"
    "心得字数逐日减少、心情持续低落、提到没劲/没意义→motivation_decay；提到生病/旅行/突发事件→external；"
    "信号不足时按motivation_decay处理。\n"
    "方案映射：task_hard→lighten3（未来3天降难度版），no_time→micro（未来7天微习惯版，每天5分钟），"
    "motivation_decay→micro，external→keep（保持原计划）。"
)

_ADJUST_TASKS_SYSTEM = (
    "你是习惯养成教练。把给定的每日任务调整为更轻松的版本，方向不变但显著降低执行门槛。"
    "只输出严格JSON，不要markdown标记："
    "{\"tasks\": [{\"day\": 1, \"title\": \"任务标题\", \"description\": \"具体任务\", \"tip\": \"小贴士\"}]}\n"
    "要求：lighten模式下任务量降到原来的三分之一；micro模式下每天只需5分钟以内的最小行动；"
    "day编号必须与原任务一致，任务数量一致。"
)


class AIService:
    async def parse_challenge_input(self, raw_input: str) -> dict[str, object]:
        llm = get_llm_service()
        raw = await llm.ask(
            raw_input,
            system=_PARSE_SYSTEM,
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

    async def generate_challenge_plan(
        self, title: str, description: str, category: str, duration: int
    ) -> dict[str, object]:
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=f"{_PLAN_SYSTEM}共{duration}天。",
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=120.0,
        )
        return self.parse_plan_text(raw, title, duration)

    async def generate_challenge_plan_stream(
        self, title: str, description: str, category: str, duration: int
    ) -> AsyncGenerator[str, None]:
        user_msg = f"挑战：{title}\n描述：{description or '无'}\n分类：{category}\n天数：{duration}"
        llm = get_llm_service()
        async for token in llm.stream_ask(
            user_msg,
            system=f"{_PLAN_SYSTEM}共{duration}天。",
            temperature=settings.PLANNING_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
        ):
            yield token

    def parse_plan_text(self, raw: str, title: str, duration: int) -> dict[str, object]:
        parsed = parse_llm_json(raw)
        if "raw_response" not in parsed and isinstance(parsed.get("plan"), list):
            return parsed
        logger.error("Plan parse failed, generating fallback")
        return {
            "plan": [
                {"day": i + 1, "title": f"第{i + 1}天", "description": f"坚持{title}", "tip": "保持动力！"}
                for i in range(duration)
            ],
            "suggestions": ["每天进步一点点", "记录你的感受", "找到你的节奏"],
        }

    async def generate_daily_feedback(
        self,
        challenge_title: str,
        day_number: int,
        total_days: int,
        mood: str,
        reflection: str,
        memory_context: str,
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
            system=_FEEDBACK_SYSTEM,
            temperature=settings.FEEDBACK_TEMPERATURE,
            max_tokens=256,
            timeout=30.0,
        )
        return raw.strip()

    async def generate_weekly_report(
        self, challenge_title: str, checkins: list[dict[str, object]], total_days: int
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
            system=_WEEKLY_SYSTEM,
            temperature=0.6,
            max_tokens=512,
            timeout=30.0,
        )
        return raw.strip()

    async def generate_repair_message(self, challenge_title: str, missed_days: int) -> str:
        user_msg = f"挑战：{challenge_title}\n断签天数：{missed_days}天"
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=_REPAIR_SYSTEM,
            temperature=0.7,
            max_tokens=128,
            timeout=20.0,
        )
        return raw.strip()

    async def generate_share_quote(self, challenge_title: str, streak: int) -> str:
        user_msg = f"挑战：{challenge_title}\n已连续坚持：{streak}天"
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=_QUOTE_SYSTEM,
            temperature=0.8,
            max_tokens=64,
            timeout=15.0,
        )
        quote = raw.strip().strip('"').strip("'").split("\n")[0].strip()
        return quote[:20] if quote else "坚持，是最好的答案"

    async def generate_declaration(self, challenge_title: str, day_number: int, streak: int) -> str:
        user_msg = f"挑战：{challenge_title}\n今天是第{day_number}天，已连续{streak}天"
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=_DECLARATION_SYSTEM,
            temperature=0.9,
            max_tokens=48,
            timeout=12.0,
        )
        text = raw.strip().strip('"').strip("'").split("\n")[0].strip()
        return text[:20]

    async def diagnose_break(
        self,
        challenge_title: str,
        missed_count: int,
        total_days: int,
        done_days: int,
        recent_summary: str,
    ) -> dict[str, object] | None:
        user_msg = (
            f"挑战：{challenge_title}（共{total_days}天，已完成{done_days}天，本次断签{missed_count}天）\n"
            f"最近打卡记录：\n{recent_summary or '暂无'}"
        )
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=_DIAGNOSIS_SYSTEM,
            temperature=0.4,
            max_tokens=384,
            timeout=30.0,
        )
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed:
            return None
        if parsed.get("cause") not in ("task_hard", "no_time", "motivation_decay", "external"):
            return None
        if parsed.get("suggestion_action") not in ("lighten3", "micro", "keep"):
            parsed["suggestion_action"] = "lighten3"
        return parsed

    async def generate_adjusted_tasks(
        self, challenge_title: str, tasks: list[dict[str, object]], mode: str
    ) -> list[dict[str, object]] | None:
        user_msg = f"挑战：{challenge_title}\n模式：{mode}\n原任务：{json.dumps(tasks, ensure_ascii=False)}"
        llm = get_llm_service()
        raw = await llm.ask(
            user_msg,
            system=_ADJUST_TASKS_SYSTEM,
            temperature=0.5,
            max_tokens=2048,
            timeout=60.0,
        )
        parsed = parse_llm_json(raw)
        if "raw_response" in parsed or not isinstance(parsed.get("tasks"), list):
            return None
        return [t for t in parsed["tasks"] if isinstance(t, dict) and t.get("title")]
