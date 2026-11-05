"""generate_adjusted_tasks ask_json 守底：契约失败重试自愈+全败兜底不变（harness r66，r64 漏网面补守底）。

纪律同 r65 三仓守底：fake 打在 get_llm_service/LLMService.ask 传输缝，
ask_json 走真原语非 mock；garbage→valid 断言 calls==2 自愈+attempt1 no_cache；
恒 garbage 断言 None 兜底不变；裸数组形态 gate 直收 calls==1 不重试。
"""
from __future__ import annotations

import json

import pytest

import app.services.ai_analysis_service as mod
from app.services.ai_analysis_service import AIAnalysisService


class _FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    async def ask(self, prompt, system=None, **kwargs):
        self.calls.append({"prompt": prompt, "system": system, **kwargs})
        if self.replies:
            return self.replies.pop(0)
        return "garbage"


def _svc(llm, monkeypatch):
    monkeypatch.setattr(mod, "get_llm_service", lambda: llm)
    return AIAnalysisService()


@pytest.mark.asyncio
async def test_retry_recovers_after_garbage(monkeypatch):
    llm = _FakeLLM(["not json at all", json.dumps({"tasks": [{"title": "散步"}]})])
    result = await _svc(llm, monkeypatch).generate_adjusted_tasks(
        "多喝水", [{"title": "旧任务"}], "lighten3",
    )
    assert result == [{"title": "散步"}]
    assert len(llm.calls) == 2
    assert "no_cache" not in llm.calls[0]
    assert llm.calls[1]["no_cache"] is True


@pytest.mark.asyncio
async def test_all_fail_keeps_none_fallback(monkeypatch):
    llm = _FakeLLM([])
    result = await _svc(llm, monkeypatch).generate_adjusted_tasks(
        "多喝水", [{"title": "旧任务"}], "lighten3",
    )
    assert result is None
    assert len(llm.calls) == 2


@pytest.mark.asyncio
async def test_bare_array_accepted_single_call(monkeypatch):
    llm = _FakeLLM(['[{"title": "深呼吸"}]'])
    result = await _svc(llm, monkeypatch).generate_adjusted_tasks(
        "多喝水", [{"title": "旧任务"}], "lighten3",
    )
    assert result == [{"title": "深呼吸"}]
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_non_title_rows_filtered(monkeypatch):
    llm = _FakeLLM([json.dumps({"tasks": [{"title": "跑"}, {"nope": 1}, "junk"]})])
    result = await _svc(llm, monkeypatch).generate_adjusted_tasks(
        "多喝水", [{"title": "旧任务"}], "lighten3",
    )
    assert result == [{"title": "跑"}]
