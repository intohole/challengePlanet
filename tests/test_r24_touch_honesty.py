"""r24 触达诚实化：normal 让位 rescue（缺席 ≥3 天）+ journey 推送静音窗门 + 毕业文案精确。"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 register all tables
from app.core import datetime_utils as cp_datetime_utils
from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import AIInsight, CheckIn
from app.services import graduation_service, reminder_service
from app.services.absence_service import absence_revive_text
from app.services.graduation_service import (
    PUSH_WINDOW_END_HOUR,
    PUSH_WINDOW_START_HOUR,
    journey_push_window_open,
)
from app.services.streak_service import shift_date, today_str
from nexus.utils.time import TimeUtils


class FakeNotifyClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, **kwargs: object) -> dict[str, object]:
        self.sent.append(kwargs)
        return {"ok": True}

    async def send_many(self, items: list[dict[str, object]]) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for item in items:
            results.append(await self.send(**item))
        return results


def _make_session():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine("sqlite+aiosqlite:///" + path)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


def _run_reminders() -> list[dict[str, object]]:
    async def main() -> list[dict[str, object]]:
        engine, Session = _make_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            uid = "1001"
            c_word = Challenge(
                user_id=uid, title="英语挑战", task_type="word", unit="词",
                direction="increase", goal_rule="fixed", target_value=20.0,
                start_date=shift_date(today_str(), -40), end_date=shift_date(today_str(), 20),
                status="active",
            )
            c_fresh = Challenge(
                user_id=uid, title="读书", task_type="page", unit="页",
                direction="increase", goal_rule="fixed", target_value=10.0,
                start_date=shift_date(today_str(), -5), end_date=shift_date(today_str(), 25),
                status="active",
            )
            c_two_day = Challenge(
                user_id=uid, title="冥想", task_type="timer", unit="分",
                direction="increase", goal_rule="fixed", target_value=10.0,
                start_date=shift_date(today_str(), -10), end_date=shift_date(today_str(), 20),
                status="active",
            )
            s.add_all([c_word, c_fresh, c_two_day])
            await s.flush()
            s.add(CheckIn(
                challenge_id=c_word.id, user_id=uid,
                timestamp=TimeUtils.now_naive(), date=shift_date(today_str(), -4),
                status="completed",
            ))
            s.add(CheckIn(
                challenge_id=c_fresh.id, user_id=uid,
                timestamp=TimeUtils.now_naive(), date=shift_date(today_str(), -1),
                status="completed",
            ))
            s.add(CheckIn(
                challenge_id=c_two_day.id, user_id=uid,
                timestamp=TimeUtils.now_naive(), date=shift_date(today_str(), -2),
                status="completed",
            ))
            await s.commit()
        fake = FakeNotifyClient()
        reminder_service.async_session = Session
        reminder_service.get_notify_client = lambda: fake
        await reminder_service.send_checkin_reminders(current_hour=reminder_service.DEFAULT_REMIND_HOUR)
        sent = list(fake.sent)
        await engine.dispose()
        return sent

    return asyncio.run(main())


# ---------- C2: normal 让位 rescue ----------

def test_absent_three_days_handed_to_rescue() -> None:
    sent = _run_reminders()
    by_kind: list[tuple[str, dict[str, object]]] = []
    for payload in sent:
        data = payload.get("data") or {}
        if data.get("rescue"):
            by_kind.append(("rescue", payload))
        elif "打卡提醒" in str(payload.get("title", "")) or "个挑战待打卡" in str(payload.get("title", "")):
            by_kind.append(("normal", payload))
    normals = [p for k, p in by_kind if k == "normal"]
    rescues = [p for k, p in by_kind if k == "rescue"]

    assert len(normals) == 1, sent
    # 缺席 1 天（读书）与缺席 2 天（冥想）留在 normal；缺席 4 天（英语挑战，rescue 口径漏 3 天）让位 rescue
    assert normals[0]["data"]["challenge_count"] == 2
    assert "英语挑战" not in str(normals[0]["title"])
    assert len(rescues) == 1, sent
    assert rescues[0]["data"]["missed_days"] == 3
    assert "断了 3 天" in str(rescues[0]["content"])
    assert "节奏有些波动" not in str(rescues[0]["content"])


def test_two_day_absence_stays_in_normal() -> None:
    sent = _run_reminders()
    normal = [p for p in sent if "打卡提醒" in str(p.get("title", "")) or "个挑战待打卡" in str(p.get("title", ""))]
    assert len(normal) == 1
    assert normal[0]["data"]["challenge_count"] == 2


# ---------- C1: journey 推送静音窗门 ----------

def test_window_predicate_aligns_platform_quiet_hours() -> None:
    assert PUSH_WINDOW_START_HOUR == 8 and PUSH_WINDOW_END_HOUR == 22
    assert journey_push_window_open(0) is False
    assert journey_push_window_open(7) is False
    assert journey_push_window_open(8) is True
    assert journey_push_window_open(12) is True
    assert journey_push_window_open(21) is True
    assert journey_push_window_open(22) is False


async def _seed_graduated(s, uid: str = "2002") -> int:
    today = today_str()
    start = shift_date(today, -20)
    ch = Challenge(
        user_id=uid, title="戒断挑战", category="quit", task_type="counter",
        unit="根", direction="decrease", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0,
    )
    s.add(ch)
    await s.flush()
    s.add(CheckIn(
        challenge_id=ch.id, user_id=uid,
        timestamp=TimeUtils.now_naive(), date=start, status="completed",
    ))
    return int(ch.id)


def _run_journey_push(hour: int) -> tuple[list[dict[str, object]], object]:
    async def main() -> tuple[list[dict[str, object]], object]:
        engine, Session = _make_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await _seed_graduated(s)
            await s.commit()
        fake = FakeNotifyClient()
        graduation_service.async_session = Session
        graduation_service.get_notify_client = lambda: fake
        fake_now = datetime(2026, 11, 1, hour, 40, 0)
        with patch.object(cp_datetime_utils, "now_china", return_value=fake_now):
            await graduation_service.GraduationPushService().send_journey_pushes()
        async with Session() as s:
            from sqlalchemy import select

            rows = list((await s.execute(
                select(AIInsight).where(AIInsight.insight_type == "journey_push")
            )).scalars().all())
            state = rows[0].content if rows else None
        await engine.dispose()
        return list(fake.sent), state

    return asyncio.run(main())


def test_graduation_push_deferred_outside_window() -> None:
    sent, state = _run_journey_push(hour=0)
    assert sent == []
    assert state is None


def test_graduation_push_sent_in_window_once() -> None:
    async def main() -> tuple[list[dict[str, object]], object, list[dict[str, object]]]:
        engine, Session = _make_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await _seed_graduated(s)
            await s.commit()
        fake = FakeNotifyClient()
        graduation_service.async_session = Session
        graduation_service.get_notify_client = lambda: fake
        svc = graduation_service.GraduationPushService()
        with patch.object(cp_datetime_utils, "now_china", return_value=datetime(2026, 11, 1, 9, 40, 0)):
            await svc.send_journey_pushes()
        first = list(fake.sent)
        with patch.object(cp_datetime_utils, "now_china", return_value=datetime(2026, 11, 1, 10, 40, 0)):
            await svc.send_journey_pushes()
        async with Session() as s:
            from sqlalchemy import select

            rows = list((await s.execute(
                select(AIInsight).where(AIInsight.insight_type == "journey_push")
            )).scalars().all())
            state = rows[0].content if rows else None
        await engine.dispose()
        return first, state, list(fake.sent)

    sent, state, all_sent = asyncio.run(main())
    assert len(sent) == 1, sent
    assert "阶梯走完了" in str(sent[0]["title"])
    assert "不会过期" in str(sent[0]["content"])
    assert state is not None and '"graduated": true' in str(state)
    assert len(all_sent) == 1


# ---------- C3: 毕业文案精确 ----------

def test_graduated_switch_lane_copy_precise() -> None:
    title, body = absence_revive_text("戒断挑战", "根", {"cap_now": 3, "avoided_total": 18}, lane="switch", graduated=True)
    assert "证书不会过期" in title
    assert "旅程档案" not in body
    assert "毕业证书一直在" in body
