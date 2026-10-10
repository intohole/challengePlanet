from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.archive import JourneyArchive
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.archive_service import archive_and_delete, best_streak, user_summary
from app.services.challenge_service import ChallengeService

import app.models.archive  # noqa: F401,F811 register table


def _mk_challenge(uid: str, **kw: object) -> Challenge:
    base: dict = dict(
        user_id=uid, title="戒烟挑战", description="", category="quit",
        task_type="counter", target_value=10.0, unit="根", direction="decrease",
        goal_type="hard", decompose_mode="none", duration_days=30,
        start_date="2026-10-01", end_date="2026-10-30", status="active",
        ai_plan="[]", color="#ef4444", icon="🚭", scene_template="",
        is_shared=False, share_token="t" * 32,
        goal_rule="ladder", goal_mode="ceiling",
        ladder_start=10.0, ladder_goal=5.0, ladder_interval=2, ladder_step=1.0,
    )
    base.update(kw)
    return Challenge(**base)


def _mk_checkin(cid: int, uid: str, d: str, value: float) -> CheckIn:
    return CheckIn(
        challenge_id=cid, user_id=uid, day_number=1, status="completed",
        timestamp=datetime.now(), date=d, value=value, unit="根", target_value=10.0,
        goal_type="hard", direction="decrease", completion_pct=100.0,
        mood="", reflection="", ai_feedback="", context_tag="",
    )


def test_best_streak() -> None:
    assert best_streak(set()) == 0
    assert best_streak({"2026-10-01", "2026-10-02", "2026-10-03"}) == 3
    assert best_streak({"2026-10-01", "2026-10-02", "2026-10-05", "2026-10-06"}) == 2
    assert best_streak({"bad-date", "2026-10-01"}) == 1


def test_archive_and_summary() -> None:
    async def main() -> None:
        from app.services.streak_service import today_str

        today = today_str()
        span = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime("2026-10-01", "%Y-%m-%d")).days
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as s:
            ch = _mk_challenge("u1")
            s.add(ch)
            await s.flush()
            s.add_all([
                _mk_checkin(ch.id, "u1", "2026-10-01", 10.0),
                _mk_checkin(ch.id, "u1", "2026-10-02", 8.0),
                _mk_checkin(ch.id, "u1", "2026-10-03", 7.0),
            ])
            await s.flush()

            summary = await archive_and_delete(s, ch)
            await s.commit()
            assert summary["completed_days"] == span
            assert summary["total_checkins"] == 3
            assert summary["streak_best"] == span
            assert summary["avoided_total"] == 5
            assert summary["baseline"] == 10.0
            assert summary["final_cap"] == 5.0
            assert summary["graduation_state"] == "approaching"

        async with Session() as s:
            rows = (await s.execute(Challenge.__table__.select())).fetchall()
            assert not rows
            archives = (await s.execute(JourneyArchive.__table__.select())).fetchall()
            assert len(archives) == 1
            assert archives[0].completed_days == span
            assert archives[0].graduation_state == "approaching"

            total = await user_summary(s, "u1")
            assert total["checkin_days"] == span
            assert total["best_streak"] == span
            assert total["avoided_total"] == 5
            assert total["archive_count"] == 1

            ch2 = _mk_challenge("u1")
            s.add(ch2)
            await s.flush()
            s.add(_mk_checkin(ch2.id, "u1", "2026-10-05", 6.0))
            await s.flush()
            total2 = await user_summary(s, "u1")
            assert total2["checkin_days"] == span * 2
            assert total2["avoided_total"] == 9
            assert total2["active_count"] == 1

    asyncio.run(main())


def test_purge_leaves_no_archive() -> None:
    async def main() -> None:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with Session() as s:
            ch = _mk_challenge("u2")
            s.add(ch)
            await s.flush()
            s.add(_mk_checkin(ch.id, "u2", "2026-10-01", 3.0))
            await s.flush()

            service = ChallengeService()
            result = await service.delete_challenge(s, ch.id, "u2", mode="purge")
            await s.commit()
            assert result["status"] == "purged"
            archives = (await s.execute(JourneyArchive.__table__.select())).fetchall()
            assert not archives

            ch3 = _mk_challenge("u2")
            s.add(ch3)
            await s.flush()
            result2 = await service.delete_challenge(s, ch3.id, "other-user")
            assert result2 is None

    asyncio.run(main())
