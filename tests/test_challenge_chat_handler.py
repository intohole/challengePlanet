"""ChallengeChatHandler 试点测试 — 验证 nexus.chat 协议表达力。

覆盖: 挑战进度/连续天数/风险检测/阶梯玩法/meta 持久化/引擎集成。
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.challenge_chat_handler import ChallengeChatHandler


@pytest.fixture
def handler() -> ChallengeChatHandler:
    return ChallengeChatHandler()


def _make_context(handler: ChallengeChatHandler, meta: dict | None = None, user_message: str = "我今天有点不想坚持了"):
    from nexus.chat.context import ChatContext
    from nexus.chat.models import ChatConversation

    conv = ChatConversation(user_id="u1", app_name="challengePlanet", meta=meta or {})
    return ChatContext(conversation=conv, user_message=user_message)


def _make_challenge(**kw: object) -> SimpleNamespace:
    defaults = dict(
        id=1, user_id="u1", title="戒烟挑战", description="", category="quit",
        task_type="binary", target_value=20.0, unit="支", direction="decrease",
        goal_type="hard", goal_rule="ladder", goal_mode="ceiling",
        ladder_start=20.0, ladder_goal=0.0, ladder_interval=3, ladder_step=1.0,
        duration_days=30, start_date="2026-08-01", end_date="2026-08-30",
        status="active", ai_plan="[]", color="#6366f1", icon="🎯",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _make_checkin(date: str, mood: str = "", pct: int = 100) -> SimpleNamespace:
    return SimpleNamespace(date=date, mood=mood, completion_pct=pct)


class FakeSession:
    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False


def _patch_db(monkeypatch, challenge: SimpleNamespace | None, checkins: list | None = None) -> None:
    from app.repositories.challenge_repository import ChallengeRepository
    from app.repositories.checkin_repository import CheckInRepository

    async def fake_get_by_id(self, session: object, challenge_id: int) -> SimpleNamespace | None:
        return challenge

    async def fake_get_checkins(self, session: object, challenge_id: int) -> list:
        return checkins or []

    monkeypatch.setattr("app.services.challenge_chat_handler.async_session", FakeSession)
    monkeypatch.setattr(ChallengeRepository, "get_by_id", fake_get_by_id)
    monkeypatch.setattr(CheckInRepository, "get_by_challenge", fake_get_checkins)


def test_default_title(handler: ChallengeChatHandler) -> None:
    assert handler.default_title == "挑战伴学"
    assert "stream" in handler.capabilities
    assert "meta" in handler.capabilities


@pytest.mark.asyncio
async def test_build_context_no_challenge(handler: ChallengeChatHandler) -> None:
    ctx = _make_context(handler, meta={})
    await handler.build_context(ctx)
    assert ctx.domain_state["error"] == "no_challenge"
    assert ctx.context_parts == []


@pytest.mark.asyncio
async def test_build_context_with_challenge(handler: ChallengeChatHandler, monkeypatch) -> None:
    challenge = _make_challenge()
    checkins = [
        _make_checkin("2026-08-14"), _make_checkin("2026-08-15"),
        _make_checkin("2026-08-16"), _make_checkin("2026-08-17"),
        _make_checkin("2026-08-18"), _make_checkin("2026-08-19"),
    ]
    _patch_db(monkeypatch, challenge, checkins)

    ctx = _make_context(handler, meta={"challenge_id": 1})
    await handler.build_context(ctx)
    state = ctx.domain_state
    assert state["challenge"].title == "戒烟挑战"
    assert state["completed_days"] == 6
    assert state["ladder_progress_pct"] is not None
    assert any("戒烟挑战" in p for p in ctx.context_parts)
    assert any("阶梯进度" in p for p in ctx.context_parts)


@pytest.mark.asyncio
async def test_build_context_not_found(handler: ChallengeChatHandler, monkeypatch) -> None:
    _patch_db(monkeypatch, None)
    ctx = _make_context(handler, meta={"challenge_id": 999})
    await handler.build_context(ctx)
    assert ctx.domain_state["error"] == "not_found"


@pytest.mark.asyncio
async def test_stream_reply_no_challenge(handler: ChallengeChatHandler) -> None:
    ctx = _make_context(handler, meta={})
    await handler.build_context(ctx)
    events = [e async for e in handler.stream_reply(ctx, [{"role": "user", "content": "hi"}])]
    texts = [e for e in events if isinstance(e, str)]
    assert texts and "挑战" in texts[0]
    assert any(isinstance(e, dict) and e.get("type") == "meta" for e in events)


@pytest.mark.asyncio
async def test_stream_reply_with_challenge(handler: ChallengeChatHandler, monkeypatch) -> None:
    challenge = _make_challenge()
    checkins = [
        _make_checkin("2026-08-16", "bad"), _make_checkin("2026-08-17", "normal"),
        _make_checkin("2026-08-18", "normal"), _make_checkin("2026-08-19", "normal"),
    ]
    _patch_db(monkeypatch, challenge, checkins)

    class FakeLLM:
        async def stream_ask(self, prompt: str, **kw: object):
            yield "没关系，记录本身就是进步"
            yield "，今天先放低要求"

    monkeypatch.setattr("app.services.challenge_chat_handler.get_llm_service", lambda: FakeLLM())

    ctx = _make_context(handler, meta={"challenge_id": 1})
    await handler.build_context(ctx)
    events = [e async for e in handler.stream_reply(ctx, [{"role": "user", "content": "我今天有点不想坚持了"}])]
    texts = [e for e in events if isinstance(e, str)]
    assert texts and "进步" in texts[0]
    meta_events = [e for e in events if isinstance(e, dict) and e.get("type") == "meta"]
    assert meta_events and meta_events[0]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_on_reply_complete_persists_meta(handler: ChallengeChatHandler, monkeypatch) -> None:
    challenge = _make_challenge()
    checkins = [
        _make_checkin("2026-08-16", "bad"), _make_checkin("2026-08-17", "normal"),
        _make_checkin("2026-08-18", "normal"), _make_checkin("2026-08-19", "normal"),
    ]
    _patch_db(monkeypatch, challenge, checkins)

    ctx = _make_context(handler, meta={"challenge_id": 1})
    await handler.build_context(ctx)
    updated = await handler.on_reply_complete(ctx, "我今天有点不想坚持了", "没关系")
    assert updated["challenge_id"] == 1
    assert updated["completed_days"] == 4
    assert updated["streak"] >= 0
    assert updated["risk_level"] in ("low", "medium", "high")
    assert updated["ladder_progress_pct"] is not None


@pytest.mark.asyncio
async def test_engine_integration(handler: ChallengeChatHandler, monkeypatch) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from nexus.chat.engine import ChatEngine

    challenge = _make_challenge()
    checkins = [
        _make_checkin("2026-08-14"), _make_checkin("2026-08-15"),
        _make_checkin("2026-08-16"), _make_checkin("2026-08-17"),
        _make_checkin("2026-08-18"), _make_checkin("2026-08-19"),
    ]
    _patch_db(monkeypatch, challenge, checkins)

    class FakeLLM:
        async def stream_ask(self, prompt: str, **kw: object):
            yield "稳住"
            yield "节奏"

    monkeypatch.setattr("app.services.challenge_chat_handler.get_llm_service", lambda: FakeLLM())

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    chat_engine = ChatEngine(engine)
    chat_engine.register("challengePlanet", handler)

    conv = await chat_engine.create_conversation("u1", "challengePlanet")
    await chat_engine.update_conversation("u1", conv.id, meta={"challenge_id": 1})

    events = []
    async for event in chat_engine.stream_message("u1", "challengePlanet", conv.id, "我今天有点不想坚持了"):
        events.append(event)

    types = [e.get("type") if isinstance(e, dict) else "str" for e in events]
    assert "delta" in types
    assert "meta" in types
    assert "done" in types

    stored = await chat_engine.store.get_conversation(conv.id)
    assert stored is not None
    assert stored.meta["challenge_id"] == 1
    assert stored.meta["completed_days"] == 6

    msgs = await chat_engine.store.list_messages(conv.id, 1, 20)
    assert msgs["total"] == 2
    assert msgs["items"][0].role == "user"
    assert msgs["items"][1].role == "assistant"

    await engine.dispose()
