"""S86 形态 A 定罪/守底：mercy.repair 的 LLM 事务窗持锁。

修复前（形态 A 在位）：action create→flush 后挂起的 LLM 让并发第二写撞 database is locked（本测试红）。
修复后（LLM 移出事务窗，写序重排）：挂起期间并发写立即成功（本测试绿）。撤修复必红。
"""
from __future__ import annotations

import asyncio
import time
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.points import StreakAction
from app.services import mercy_service as mercy_mod
from app.services.mercy_service import ACTION_REPAIR, MercyService

CHALLENGE_ID = 101
OWNER = "u1"
TODAY = date(2026, 11, 2)
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()
START = (TODAY - timedelta(days=30)).isoformat()
END = (TODAY + timedelta(days=30)).isoformat()


async def _make_db(path: str):
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _hang_repair(tmp_path: str) -> tuple[bool, float, int]:
    engine, sm = await _make_db(f"{tmp_path}/s86_cp.db")
    try:
        async with sm() as s0:
            s0.add(Challenge(id=CHALLENGE_ID, user_id=OWNER, title="晨跑", start_date=START, end_date=END))
            s0.add(StreakAction(challenge_id=CHALLENGE_ID, user_id=OWNER, action="checkin",
                                action_date=START, cost=0))
            await s0.commit()
    finally:
        pass

    svc = MercyService()
    entered, hang = asyncio.Event(), asyncio.Event()

    async def hung_llm(*args, **kwargs):
        entered.set()
        await hang.wait()
        return "msg"

    async def fake_owned(session, challenge_id, user_id):
        result = await session.execute(select(Challenge).where(Challenge.id == challenge_id))
        return result.scalar_one()

    async def fake_valid(session, challenge_id):
        days = []
        cur = date.fromisoformat(START)
        while cur < date.fromisoformat(YESTERDAY):
            days.append(cur.isoformat())
            cur += timedelta(days=1)
        return set(days)

    async def fake_count(session, challenge_id, action, month_prefix):
        return 0

    svc._ai.generate_repair_message = hung_llm
    svc._get_owned_challenge = fake_owned
    svc._valid_dates = fake_valid
    svc._action_repo.count_challenge_actions_in_month = fake_count

    async with sm() as sa:
        # repair 内部用真实时钟（today_str=now_china）；测试日期写死会让「昨天断签」
        # 相对语义随日历漂移过期（11-02 写死的 TODAY 跑在 11-05 即腐化：streak_before
        # 落空→校验 ValueError→task 死→entered 永不 set→超时）。钉死被测时钟。
        with patch.object(mercy_mod, "today_str", lambda: TODAY.isoformat()):
            task = asyncio.create_task(svc.repair(sa, CHALLENGE_ID, OWNER))
            await asyncio.wait_for(entered.wait(), timeout=5)
            t0 = time.monotonic()
            locked = False
            async with sm() as sb:
                try:
                    sb.add(StreakAction(challenge_id=CHALLENGE_ID + 1, user_id="u2",
                                        action="checkin", action_date=YESTERDAY, cost=0))
                    await asyncio.wait_for(sb.commit(), timeout=9)
                except (OperationalError, asyncio.TimeoutError):
                    locked = True
                await sb.rollback()
            dt = time.monotonic() - t0
            hang.set()
            await asyncio.wait_for(task, timeout=5)
            await sa.commit()

    async with sm() as sc:
        n = len((await sc.execute(select(StreakAction))).scalars().all())
    await engine.dispose()
    return locked, dt, n


@pytest.mark.asyncio
async def test_repair_llm_txn_window(tmp_path: str) -> None:
    locked, dt, n = await _hang_repair(str(tmp_path))
    assert not locked and dt < 2.5, (
        f"mercy.repair LLM 挂起窗并发写被锁: locked={locked} blocked={dt:.2f}s（形态 A 在位=action flush 持锁横跨 LLM）"
    )
    assert n == 3, f"修复动作与种子行终态在库: rows={n}"
