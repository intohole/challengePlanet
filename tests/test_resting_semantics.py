from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 register all tables
from app.core.datetime_utils import now_china
from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.models.reminder import TouchState
from app.services.challenge_service import ChallengeService
from app.services.streak_service import shift_date, today_str
from app.services import touch_gate_service


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


def _mk_challenge(user_id: str = "2", status: str = "active", **kw) -> dict[str, object]:
    return {
        "user_id": user_id, "title": kw.get("title", "英语挑战"),
        "category": "learn", "duration_days": 66,
        "start_date": kw.get("start_date", "2026-09-09"),
        "end_date": kw.get("end_date", shift_date("2026-09-09", 65)),
        "status": status, "task_type": "binary", "target_value": 1.0, "unit": "次",
    }


def _mk_checkin(challenge_id: int, user_id: str, day: str, day_number: int = 1) -> dict[str, object]:
    return {
        "challenge_id": challenge_id, "user_id": user_id, "day_number": day_number,
        "status": "kept", "timestamp": now_china(), "date": day,
        "value": 1.0, "unit": "次", "target_value": 1.0,
        "goal_type": "hard", "direction": "increase",
    }


def test_episode_over_boundaries() -> None:
    today = "2026-11-09"
    assert touch_gate_service.episode_over("2026-10-10", today) is True
    assert touch_gate_service.episode_over("2026-10-09", today) is True
    assert touch_gate_service.episode_over("2026-10-11", today) is False
    assert touch_gate_service.episode_over("", today) is False


def test_gate_consumes_shared_episode_over(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> str:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="rescue", challenge_id=4, user_id="2",
                episode_anchor="2026-10-04", today="2026-11-09",
            )
            await engine.dispose()
            return str(gate["action"])

    assert _run(main()) == "sunset"


def test_gate_episode_over_not_bypassed_by_inline_formula(session_factory, monkeypatch) -> None:
    engine, Session = session_factory()

    async def main() -> str:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            monkeypatch.setattr(touch_gate_service, "episode_over", lambda a, t: False)
            gate = await touch_gate_service.decide_touch_kind(
                s, kind="rescue", challenge_id=4, user_id="2",
                episode_anchor="2026-10-04", today="2026-11-09",
            )
            await engine.dispose()
            return str(gate["action"])

    assert _run(main()) != "sunset"


def test_close_resting_migrates_missing_over_30d(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> tuple[int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            zomb = Challenge(**_mk_challenge())
            fresh = Challenge(**_mk_challenge(title="新挑战", start_date=today_str(), end_date=shift_date(today_str(), 65)))
            s.add_all([zomb, fresh])
            await s.flush()
            s.add(CheckIn(**_mk_checkin(zomb.id, "2", "2026-10-04")))
            s.add(CheckIn(**_mk_checkin(fresh.id, "2", today_str())))
            await s.commit()
            rested = await ChallengeService().close_resting(s)
            await s.refresh(zomb)
            await s.refresh(fresh)
            await engine.dispose()
            return rested, sum(1 for c in (zomb, fresh) if c.status == "resting")

    rested, resting_count = _run(main())
    assert rested == 1
    assert resting_count == 1


def test_close_resting_spares_never_started(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> str:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            ch = Challenge(**_mk_challenge(start_date=today_str(), end_date=shift_date(today_str(), 65)))
            s.add(ch)
            await s.commit()
            await ChallengeService().close_resting(s)
            await s.refresh(ch)
            await engine.dispose()
            return str(ch.status)

    assert _run(main()) == "active"


def test_close_resting_idempotent(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> tuple[int, int]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            ch = Challenge(**_mk_challenge())
            s.add(ch)
            await s.flush()
            s.add(CheckIn(**_mk_checkin(ch.id, "2", "2026-10-04")))
            await s.commit()
            first = await ChallengeService().close_resting(s)
            second = await ChallengeService().close_resting(s)
            await engine.dispose()
            return first, second

    first, second = _run(main())
    assert first == 1
    assert second == 0


def test_revive_resets_episode_and_clears_touch_state(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> dict[str, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            ch = Challenge(**_mk_challenge(status="resting"))
            s.add(ch)
            await s.flush()
            s.add(TouchState(user_id="2", challenge_id=ch.id, kind="rescue",
                             fingerprint="x", last_notif_id=99, last_action="revive"))
            await s.commit()
            result = await ChallengeService().revive_challenge(s, ch.id, "2")
            await s.refresh(ch)
            states = (await s.execute(__import__("sqlalchemy").select(TouchState))).scalars().all()
            await engine.dispose()
            return {
                "revived": result.get("revived") if result else False,
                "status": ch.status,
                "start_date": ch.start_date,
                "end_date": ch.end_date,
                "touch_states": len(list(states)),
            }

    r = _run(main())
    assert r["revived"] is True
    assert r["status"] == "active"
    assert r["start_date"] == today_str()
    assert r["end_date"] == shift_date(today_str(), 65)
    assert r["touch_states"] == 0


def test_revive_rejects_active_and_other_user(session_factory) -> None:
    engine, Session = session_factory()

    async def main() -> tuple[object, object]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            ch = Challenge(**_mk_challenge(status="active"))
            s.add(ch)
            await s.flush()
            svc = ChallengeService()
            active_try = await svc.revive_challenge(s, ch.id, "2")
            other_try = await svc.revive_challenge(s, ch.id, "999")
            await engine.dispose()
            return active_try, other_try

    active_try, other_try = _run(main())
    assert active_try is not None and active_try.get("revived") is False
    assert other_try is None


def test_revived_challenge_not_re_resting_by_stale_anchor(session_factory) -> None:
    """复活后旧 last_seen 不得把新 episode 打回 resting（r26 E2E 掀出的真 bug 守底）。

    场景：resting 挑战复活（start_date=今天，历史打卡保留在 36 天前）——
    close_resting 的锚取 max(last_seen, start_date)，新起点 30 天内不迁移。
    gate 层同族：effective_anchor 抬升让指纹变化（新 episode 自动解除）。
    """
    engine, Session = session_factory()

    async def main() -> str:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            today = today_str()
            ch = Challenge(**_mk_challenge(status="resting", start_date=today,
                                           end_date=shift_date(today, 65)))
            s.add(ch)
            await s.flush()
            s.add(CheckIn(**_mk_checkin(ch.id, "2", "2026-10-04")))
            await s.commit()
            svc = ChallengeService()
            assert (await svc.revive_challenge(s, ch.id, "2") or {}).get("revived") is True
            await svc.close_resting(s)
            await s.refresh(ch)
            await engine.dispose()
            return str(ch.status)

    assert _run(main()) == "active"


def test_effective_anchor_floor_semantics() -> None:
    f = touch_gate_service.effective_anchor
    assert f("2026-10-04", "2026-11-09") == "2026-11-09"
    assert f("2026-11-09", "2026-10-04") == "2026-11-09"
    assert f("", "2026-11-09") == "2026-11-09"
    assert f("2026-10-04", "") == "2026-10-04"
    assert f("", "") == ""
