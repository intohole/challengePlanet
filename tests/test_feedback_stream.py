from __future__ import annotations

import json

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.schemas.checkin import FeedbackStreamRequest
from app.services.checkin_service import CheckInService
from app.services.streak_service import shift_date, today_str


async def _make_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    return engine, maker


def _add_challenge(session, **kw) -> Challenge:
    ch = Challenge(
        user_id="u1", title="戒烟", category="quit", task_type="counter", unit="根",
        direction="decrease", goal_type="soft", goal_rule="fixed",
        duration_days=14, status="active",
        target_value=5.0, ai_plan="[]", share_token="tfb", color="#ef4444", icon="🚭",
        **kw,
    )
    session.add(ch)
    return ch


def _fake_stream(pieces: list[str]):
    async def _gen(**kw):
        for p in pieces:
            yield p
    return _gen


async def _collect_sse(response) -> list[dict]:
    events: list[dict] = []
    async for chunk in response.body_iterator:
        for line in str(chunk).strip().splitlines():
            if line.startswith("data:"):
                events.append(json.loads(line[5:].strip()))
    return events


async def _fake_declaration(*a, **k):
    return "少抽一根，赢回一天"


@pytest.mark.asyncio
async def test_stream_feedback_generates_and_persists(monkeypatch) -> None:
    from app.api.checkin import stream_feedback

    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        r = await CheckInService().do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        cid = r["checkin"].id

        async def fake_inputs(sess, checkin, challenge):
            return {
                "challenge_title": challenge.title, "day_number": checkin.day_number,
                "total_days": challenge.duration_days, "mood": checkin.mood,
                "reflection": checkin.reflection, "memory_context": "",
                "value": 1.0, "target": 5.0, "direction": "decrease",
                "is_soft_exceeded": False,
            }

        monkeypatch.setattr("app.services.checkin_stream_service.build_feedback_prompt_inputs", fake_inputs)
        monkeypatch.setattr(
            "app.services.checkin_stream_service.AIService",
            type("FakeAI", (), {
                "stream_daily_feedback": staticmethod(_fake_stream(["今天辛苦了，", "记下来就好"])),
                "_feedback_system": staticmethod(lambda mood: "SYS"),
            }),
        )
        monkeypatch.setattr("app.services.checkin_stream_service.safe_declaration", _fake_declaration)

        resp = await stream_feedback(
            ch.id, FeedbackStreamRequest(checkin_id=cid),
            user_id="u1", session=session,
        )
        events = await _collect_sse(resp)
        tokens = [d for d in events if d.get("type") == "token"]
        dones = [d for d in events if d.get("type") == "done"]
        assert len(tokens) == 2
        assert dones and dones[-1]["content"] == "今天辛苦了，记下来就好"
        assert dones[-1]["declaration"] == "少抽一根，赢回一天"
        assert r["checkin"].ai_feedback == "今天辛苦了，记下来就好"
        assert r["checkin"].declaration == "少抽一根，赢回一天"


@pytest.mark.asyncio
async def test_stream_feedback_cached_short_circuit(monkeypatch) -> None:
    from app.api.checkin import stream_feedback

    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        r = await CheckInService().do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        await CheckInService()._repo.update(session, r["checkin"], {"ai_feedback": "已有反馈", "declaration": "宣言"})
        await session.commit()

        called = {"n": 0}

        def _boom(**kw):
            called["n"] += 1
            raise AssertionError("不应触发 AI")

        monkeypatch.setattr("app.services.checkin_stream_service.AIService", type("FakeAI", (), {"stream_daily_feedback": staticmethod(_boom)}))
        resp = await stream_feedback(
            ch.id, FeedbackStreamRequest(checkin_id=cid),
            user_id="u1", session=session,
        )
        events = await _collect_sse(resp)
        assert not [d for d in events if d.get("type") == "token"]
        dones = [d for d in events if d.get("type") == "done"]
        assert dones[0]["content"] == "已有反馈"
        assert dones[0]["cached"] is True
        assert called["n"] == 0


@pytest.mark.asyncio
async def test_stream_feedback_rejects_foreign_challenge() -> None:
    from app.api.checkin import stream_feedback

    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        r = await CheckInService().do_checkin(session, ch.id, "u1", value=1.0)
        with pytest.raises(HTTPException) as exc:
            await stream_feedback(
                ch.id, FeedbackStreamRequest(checkin_id=r["checkin"].id),
                user_id="u2", session=session,
            )
        assert exc.value.status_code == 400
