from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services import reminder_service

import app.models  # noqa: F401 register all tables


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


def _run() -> list[dict[str, object]]:
    async def main() -> list[dict[str, object]]:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        engine = create_async_engine("sqlite+aiosqlite:///" + path)
        Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        fake = FakeNotifyClient()
        reminder_service.async_session = Session
        reminder_service.get_notify_client = lambda: fake
        today = reminder_service.today_str()

        async with Session() as s:
            uid = "1001"
            uid2 = "2002"
            uid_end = "4004"
            c_a = Challenge(user_id=uid, title="跑步", status="active")
            c_b = Challenge(user_id=uid, title="读书", status="active")
            c_done = Challenge(user_id=uid, title="冥想", status="active")
            c_solo = Challenge(user_id=uid2, title="早起", status="active")
            c_ended = Challenge(user_id=uid_end, title="已结束", status="ended")
            s.add_all([c_a, c_b, c_done, c_solo, c_ended])
            await s.flush()
            s.add(
                CheckIn(
                    challenge_id=c_done.id,
                    user_id=uid,
                    timestamp=datetime.now(),
                    date=today,
                    status="completed",
                )
            )
            await s.commit()

        await reminder_service.send_checkin_reminders()
        sent = list(fake.sent)
        await engine.dispose()
        return sent

    return asyncio.run(main())


def test_reminder_aggregates_per_user() -> None:
    sent = _run()
    assert len(sent) == 2, sent
    by_user: dict[str, list[dict[str, object]]] = {}
    for payload in sent:
        by_user.setdefault(str(payload["user_id"]), []).append(payload)

    multi = by_user["1001"]
    assert len(multi) == 1, multi
    assert multi[0]["data"]["challenge_count"] == 2, multi
    assert multi[0]["title"] == "2 个挑战待打卡", multi
    assert multi[0]["link"] == "/challengePlanet/", multi
    assert multi[0]["channels"] == ["in_app", "email"], multi
    assert str(multi[0]["content"]).startswith("你有 2 个挑战今天还没打卡，"), multi

    solo = by_user["2002"]
    assert len(solo) == 1, solo
    assert solo[0]["data"]["challenge_count"] == 1, solo
    assert solo[0]["title"] == "「早起」打卡提醒", solo


def test_reminder_skips_checked_and_ended() -> None:
    sent = _run()
    assert len(sent) == 2, sent
    for payload in sent:
        assert payload["user_id"] in ("1001", "2002"), payload