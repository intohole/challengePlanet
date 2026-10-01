from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.repositories.checkin_repository import CheckInRepository
from app.services.checkin_service import CheckInService
from app.services.report_service import ReportService
from app.services.streak_service import today_str, shift_date


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
        target_value=5.0, ai_plan="[]", share_token="tctx", color="#ef4444", icon="🚭",
        **kw,
    )
    session.add(ch)
    return ch


@pytest.mark.asyncio
async def test_checkin_stores_context_tag() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        r = await CheckInService().do_checkin(session, ch.id, "u1", value=2.0, context_tag="work")
        assert r["checkin"].context_tag == "work"
        assert r["today_total"] == 2.0


@pytest.mark.asyncio
async def test_update_context_tag_roundtrip() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        svc = CheckInService()
        r = await svc.do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        updated = await svc.update_context_tag(session, ch.id, cid, "u1", "stress")
        assert updated.context_tag == "stress"
        cleared = await svc.update_context_tag(session, ch.id, cid, "u1", "")
        assert cleared.context_tag == ""


@pytest.mark.asyncio
async def test_update_context_tag_guards() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        svc = CheckInService()
        r = await svc.do_checkin(session, ch.id, "u1", value=1.0)
        cid = r["checkin"].id
        with pytest.raises(ValueError):
            await svc.update_context_tag(session, ch.id, cid, "u1", "party")
        with pytest.raises(ValueError):
            await svc.update_context_tag(session, ch.id, cid, "u2", "home")
        with pytest.raises(ValueError):
            await svc.update_context_tag(session, 9999, cid, "u1", "home")
        repo = CheckInRepository()
        old = await repo.create(session, {
            "challenge_id": ch.id, "user_id": "u1", "day_number": 1,
            "status": "completed", "timestamp": datetime.fromisoformat(shift_date(today, -1) + "T10:00:00"),
            "date": shift_date(today, -1), "value": 1.0, "unit": ch.unit,
        })
        with pytest.raises(ValueError):
            await svc.update_context_tag(session, ch.id, old.id, "u1", "home")


@pytest.mark.asyncio
async def test_context_distribution_aggregates() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -9), end_date=shift_date(today, 4))
        await session.commit()
        svc = CheckInService()
        await svc.do_checkin(session, ch.id, "u1", value=3.0, context_tag="work")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, context_tag="work")
        await svc.do_checkin(session, ch.id, "u1", value=1.0, context_tag="home")
        dist = await ReportService().get_context_distribution(session, ch.id, "u1", days=30)
        assert dist["direction"] == "decrease"
        assert dist["dominant"] == "work"
        items = dist["items"]
        assert items[0]["context_tag"] == "work"
        assert items[0]["total_value"] == 4.0
        assert items[0]["checkin_count"] == 2
        assert items[0]["label"] == "工作"
        total_share = sum(i["share_pct"] for i in items)
        assert abs(total_share - 100.0) < 0.1
        assert "工作" in (dist["insight"] or "")


@pytest.mark.asyncio
async def test_context_distribution_empty() -> None:
    engine, maker = await _make_session()
    async with maker() as session:
        today = today_str()
        ch = _add_challenge(session, start_date=shift_date(today, -2), end_date=shift_date(today, 11))
        await session.commit()
        dist = await ReportService().get_context_distribution(session, ch.id, "u1", days=30)
        assert dist["items"] == []
        assert dist["dominant"] == ""
        assert dist["insight"] == ""
