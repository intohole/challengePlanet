from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.services.checkin_service import CheckInService
from app.services.report_service import ReportService
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
        target_value=5.0, ai_plan="[]", share_token="tmood", color="#ef4444", icon="🚭",
        **kw,
    )
    session.add(ch)
    return ch


@pytest.mark.asyncio
async def test_checkin_stores_mood() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        r = await CheckInService().do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        assert r["checkin"].mood == "bad"


@pytest.mark.asyncio
async def test_update_meta_mood_and_context() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        svc = CheckInService()
        r = await svc.do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        updated = await svc.update_checkin_meta(session, ch.id, cid, "u1", mood="bad")
        assert updated.mood == "bad"
        updated = await svc.update_checkin_meta(session, ch.id, cid, "u1", context_tag="stress")
        assert updated.mood == "bad" and updated.context_tag == "stress"


@pytest.mark.asyncio
async def test_update_meta_rejects_invalid() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        svc = CheckInService()
        r = await svc.do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        with pytest.raises(ValueError):
            await svc.update_checkin_meta(session, ch.id, cid, "u1")
        with pytest.raises(ValueError):
            await svc.update_checkin_meta(session, ch.id, cid, "u1", mood="angry")
        with pytest.raises(ValueError):
            await svc.update_checkin_meta(session, ch.id, cid, "u1", context_tag="space")


@pytest.mark.asyncio
async def test_update_meta_rejects_past_checkin() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -9), end_date=shift_date(today, 4))
        await session.commit()
        svc = CheckInService()
        r = await svc.do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        r["checkin"].date = shift_date(today, -1)
        with pytest.raises(ValueError):
            await svc.update_checkin_meta(session, ch.id, cid, "u1", mood="bad")


@pytest.mark.asyncio
async def test_bad_mood_triggers_adaptive_suggestion(monkeypatch) -> None:
    from app.services import adaptive_service

    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        svc = CheckInService()
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="bad")

        async def fake_ai_adjust(title, tasks, mode):
            return [{"day": 1, "title": tasks[0].get("title", "任务"), "description": "轻松版", "tip": ""}]

        monkeypatch.setattr(adaptive_service.AIService, "generate_adjusted_tasks", fake_ai_adjust)
        monkeypatch.setattr(adaptive_service, "async_session", maker)
        await adaptive_service.evaluate_after_bad_mood_task(ch.id)
        pending = await adaptive_service.AdaptiveRepository().get_pending(session, ch.id)
        assert pending is not None
        assert pending.kind == "lighten"


@pytest.mark.asyncio
async def test_mood_distribution_aggregates() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -9), end_date=shift_date(today, 4))
        await session.commit()
        svc = CheckInService()
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="bad")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="good")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, mood="good")
        dist = await ReportService().get_mood_distribution(session, ch.id, "u1", days=30)
        assert dist["dominant"] == "bad"
        items = dist["items"]
        assert items[0]["mood"] == "bad"
        assert items[0]["checkin_count"] == 3
        assert items[0]["share_pct"] == 60.0
        labels = {i["mood"]: i["label"] for i in items}
        assert labels["bad"] == "有点难"
        assert "减负" in (dist["insight"] or "") or "计划" in (dist["insight"] or "")


@pytest.mark.asyncio
async def test_mood_distribution_empty() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        dist = await ReportService().get_mood_distribution(session, ch.id, "u1", days=30)
        assert dist["items"] == []
        assert dist["dominant"] == ""
        assert dist["insight"] == ""
