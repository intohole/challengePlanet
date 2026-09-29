from __future__ import annotations

from nexus import parse_llm_json_or


def parse_ai_plan(raw: str | None) -> list[dict[str, object]]:
    plan = parse_llm_json_or(raw or "", [])
    return plan if isinstance(plan, list) else []
