"""r25 召回触达时效性：absence/rescue 豁免「偏好小时」挂 humane 窗口 [8,22)。

生产实锤（11-03）：毕业 REVIVE 21:00 gate 决策被偏好小时过滤拖到次日 20:00
送达（迟到 23h）——决策钟（每小时）与发送钟（偏好小时）解耦的断链。
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 register all tables
from app.db.database import Base
from app.models.checkin import CheckIn
from app.models.reminder import ReminderPref, TouchState
from app.services import reminder_service
from app.services.graduation_service import journey_push_window_open
from app.services.reminder_service import _prefers_now, _recall_allowed
from app.services.streak_service import shift_date, today_str
from nexus.touch import fingerprint
from nexus.utils.time import TimeUtils


class FakeNotifyClient:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []

    async def send(self, **kwargs: object) -> dict[str, object]:
        self.sent.append(kwargs)
        return {"ok": True, "status": "sent", "id": 9901}

    async def send_many(self, items: list[dict[str, object]]) -> list[dict[str, object]]:
        return [await self.send(**item) for item in items]


def _make_session():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_async_engine("sqlite+aiosqlite:///" + path)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session


def _pref(hour: int, enabled: bool = True) -> ReminderPref:
    return ReminderPref(user_id="1001", remind_hour=hour, enabled=enabled)


# ---------- 谓词单元 ----------

def test_recall_allowed_follows_humane_window_not_preference() -> None:
    assert journey_push_window_open(21) is True
    assert _recall_allowed(_pref(20), 21) is True
    assert _recall_allowed(_pref(9), 10) is True
    assert _recall_allowed(None, 21) is True
    assert _recall_allowed(_pref(20), 22) is False
    assert _recall_allowed(_pref(20), 7) is False
    assert _recall_allowed(_pref(20), 0) is False


def test_recall_respects_user_disabled() -> None:
    assert _recall_allowed(_pref(20, enabled=False), 12) is False


def test_normal_still_follows_preference_hour() -> None:
    assert _prefers_now(_pref(20), 20) is True
    assert _prefers_now(_pref(20), 21) is False


# ---------- 行为级：复现 11-03 案例形态 ----------

async def _seed_absence_revive(s: AsyncSession) -> None:
    """ladder cap 挑战缺席 10 天+同 episode 首触 8 天前 → absence 引擎判 REVIVE。"""
    uid = "1001"
    today = today_str()
    start = shift_date(today, -20)
    ch = _ladder_challenge(uid, start)
    s.add(ch)
    await s.flush()
    last_record = shift_date(today, -10)
    s.add(CheckIn(
        challenge_id=ch.id, user_id=uid,
        timestamp=TimeUtils.now_naive(), date=last_record, status="completed",
    ))
    s.add(TouchState(
        user_id=uid, challenge_id=int(ch.id), kind="absence",
        fingerprint=fingerprint("absence", int(ch.id), last_record),
        last_sent_at=TimeUtils.now_naive() - timedelta(days=8), last_notif_id=0,
        last_action="send",
    ))
    s.add(ReminderPref(user_id=uid, remind_hour=20, enabled=True))


def _ladder_challenge(uid: str, start: str):
    from app.models.challenge import Challenge

    return Challenge(
        user_id=uid, title="戒断挑战", category="quit", task_type="counter",
        unit="根", direction="decrease", goal_rule="ladder",
        ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        duration_days=66, start_date=start, end_date=shift_date(start, 65),
        status="active", target_value=1.0,
    )


async def _seed_rescue(s: AsyncSession) -> None:
    """fixed 挑战 rescue 口径缺席 3 天（首发门槛恒 due，避开隔日/周二五 cadence 对日期的依赖）。"""
    uid = "1001"
    today = today_str()
    start = shift_date(today, -20)
    ch = _fixed_challenge(uid, start)
    s.add(ch)
    await s.flush()
    s.add(CheckIn(
        challenge_id=ch.id, user_id=uid,
        timestamp=TimeUtils.now_naive(), date=shift_date(today, -4), status="completed",
    ))
    s.add(ReminderPref(user_id=uid, remind_hour=20, enabled=True))


def _fixed_challenge(uid: str, start: str):
    from app.models.challenge import Challenge

    return Challenge(
        user_id=uid, title="英语挑战", category="learn", task_type="word",
        unit="词", direction="increase", goal_rule="fixed", target_value=20.0,
        duration_days=60, start_date=start, end_date=shift_date(start, 59),
        status="active",
    )


def _run_at(hour: int, seeder) -> list[dict[str, object]]:
    async def main() -> list[dict[str, object]]:
        engine, Session = _make_session()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with Session() as s:
            await seeder(s)
            await s.commit()
        fake = FakeNotifyClient()
        reminder_service.async_session = Session
        reminder_service.get_notify_client = lambda: fake
        await reminder_service.send_checkin_reminders(current_hour=hour)
        sent = list(fake.sent)
        await engine.dispose()
        return sent

    return asyncio.run(main())


def test_revive_fires_at_nonpreferred_hour_inside_window() -> None:
    """核心复现：REVIVE 到期 21:00（偏好 20 点）→ 当节拍即发，不再等次日偏好小时。"""
    sent = _run_at(21, _seed_absence_revive)
    absence = [p for p in sent if (p.get("data") or {}).get("absence_care")]
    assert len(absence) == 1, sent
    assert absence[0]["data"]["touch_action"] == "revive"
    assert absence[0]["link"].endswith("rc=revive")


def test_recall_held_outside_humane_window() -> None:
    """窗口外（23 点）不发送——决策幂等，次日首个窗口 tick 自然补发。"""
    sent = _run_at(23, _seed_absence_revive)
    assert sent == [], sent


def test_recall_disabled_user_not_touched() -> None:
    async def seed_disabled(s: AsyncSession) -> None:
        await _seed_absence_revive(s)
        rows = list((await s.execute(
            __import__("sqlalchemy").select(ReminderPref)
        )).scalars().all())
        for row in rows:
            row.enabled = False

    sent = _run_at(21, seed_disabled)
    assert sent == [], sent


def test_rescue_fires_at_nonpreferred_hour_inside_window() -> None:
    """rescue 同通道豁免：首发到期（missed=3）的 fixed 挑战在窗口内非偏好小时即发。"""
    sent = _run_at(10, _seed_rescue)
    rescues = [p for p in sent if (p.get("data") or {}).get("rescue")]
    assert len(rescues) == 1, sent
    assert rescues[0]["data"]["missed_days"] == 3


def test_normal_ordinary_hour_without_recall_stays_silent() -> None:
    """普通 fixed 挑战+非偏好小时+无召回项 → normal 不发（偏好语义不变）。"""
    sent = _run_at(21, _seed_rescue)
    normals = [p for p in sent if not (p.get("data") or {}).get("rescue")]
    assert normals == [], sent
