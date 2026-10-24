from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 register all tables
from app.core.datetime_utils import now_china
from app.db.database import Base
from app.models.reminder import TouchState
from app.services import touch_gate_service
from app.services.streak_service import shift_date, today_str


@pytest.fixture()
def session_factory():
    def _make():
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        return engine, Session

    return _make


def _run(coro):
    return asyncio.run(coro)


def _fp(kind: str, challenge_id: int, anchor: str) -> str:
    return touch_gate_service.fingerprint(kind, challenge_id, anchor)


def test_gate_first_touch_in_episode(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="absence", challenge_id=7, user_id="2",
                episode_anchor="2026-10-16", today=today_str(),
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "send"
    assert gate["reason"] == "first_touch_in_episode"


def test_gate_silence_same_episode_recent(session_factory) -> None:
    engine, Session = session_factory()
    fp = _fp("absence", 7, "2026-10-16")

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            s.add(TouchState(
                user_id="2", challenge_id=7, kind="absence", fingerprint=fp,
                last_sent_at=now_china() - timedelta(days=2),
            ))
            await s.flush()
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="absence", challenge_id=7, user_id="2",
                episode_anchor="2026-10-16", today=today_str(),
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "silence"


def test_gate_revive_after_seven_days(session_factory) -> None:
    engine, Session = session_factory()
    fp = _fp("rescue", 4, "2026-10-08")

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            s.add(TouchState(
                user_id="2", challenge_id=4, kind="rescue", fingerprint=fp,
                last_sent_at=now_china() - timedelta(days=8), last_notif_id=0,
            ))
            await s.flush()
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="rescue", challenge_id=4, user_id="2",
                episode_anchor="2026-10-08", today=today_str(),
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "revive"
    assert gate["lane"] == "door"


def test_gate_revive_lane_switch_when_last_was_read(session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    async def _read(_notif_id: int) -> bool:
        return False

    monkeypatch.setattr(touch_gate_service, "_is_unread", _read)
    engine, Session = session_factory()
    fp = _fp("absence", 7, "2026-10-16")

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            s.add(TouchState(
                user_id="2", challenge_id=7, kind="absence", fingerprint=fp,
                last_sent_at=now_china() - timedelta(days=9), last_notif_id=1234,
            ))
            await s.flush()
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="absence", challenge_id=7, user_id="2",
                episode_anchor="2026-10-16", today=today_str(),
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "revive"
    assert gate["lane"] == "switch"


def test_gate_sunset_episode_over_30_days(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            s.add(TouchState(
                user_id="2", challenge_id=9, kind="rescue",
                fingerprint=_fp("rescue", 9, "2026-09-01"),
                last_sent_at=now_china() - timedelta(days=3),
            ))
            await s.flush()
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="rescue", challenge_id=9, user_id="2",
                episode_anchor="2026-09-01", today=today_str(),
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "sunset"
    assert "30" in str(gate["reason"])


def test_gate_legacy_insight_prevents_duplicate_first_care(session_factory) -> None:
    """TouchState 上线前的存量 episode（10-19 已 care）不得被当新 episode 重发首触。"""
    engine, Session = session_factory()
    legacy_sent = now_china() - timedelta(days=5)

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="absence", challenge_id=101, user_id="2",
                episode_anchor="2026-10-16", today=today_str(),
                legacy_sent_at=legacy_sent,
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "silence"


def test_gate_legacy_over_seven_days_revives(session_factory) -> None:
    engine, Session = session_factory()
    legacy_sent = now_china() - timedelta(days=7)

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="absence", challenge_id=101, user_id="2",
                episode_anchor="2026-10-16", today=today_str(),
                legacy_sent_at=legacy_sent,
            )
            await engine.dispose()
            return gate

    gate = _run(main())
    assert gate["action"] == "revive"


def test_mark_touch_sent_upserts(session_factory) -> None:
    engine, Session = session_factory()
    fp = _fp("rescue", 4, "2026-10-08")

    async def main() -> tuple[TouchState | None, TouchState | None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await touch_gate_service.mark_touch_sent(
                s, user_id="2", challenge_id=4, kind="rescue",
                fingerprint_value=fp, notif_id=99, action="send",
            )
            await s.commit()
            row = (await s.execute(select(TouchState))).scalar_one()
            first_notif = int(row.last_notif_id)
            await touch_gate_service.mark_touch_sent(
                s, user_id="2", challenge_id=4, kind="rescue",
                fingerprint_value=fp, notif_id=100, action="revive",
            )
            await s.commit()
            rows = (await s.execute(select(TouchState))).scalars().all()
            await engine.dispose()
            return first_notif, rows

    first_notif, rows = _run(main())
    assert first_notif == 99
    assert len(rows) == 1, "同键应 upsert 而非新增行"
    assert rows[0].last_notif_id == 100
    assert rows[0].last_action == "revive"


def test_fingerprint_changes_with_episode() -> None:
    today = today_str()
    assert _fp("rescue", 4, "2026-10-08") != _fp("rescue", 4, "2026-10-01")
    assert _fp("rescue", 4, "2026-10-08") == _fp("rescue", 4, "2026-10-08")
    assert _fp("rescue", 4, today) != _fp("absence", 4, today)
