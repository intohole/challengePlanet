#!/usr/bin/env python3
"""集成测试: 预测驱动主动提醒(风险触发/去重/多渠道)"""
from __future__ import annotations

import os
import sys
import tempfile

tmpdir = tempfile.mkdtemp(prefix="cp_alert_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmpdir}/test.db"
sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

import asyncio
from datetime import datetime

from app.db.database import async_session, init_db
from app.models.checkin import CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.services import forecast_alert_service as fas
from app.services.streak_service import shift_date, today_str

sent: list[dict] = []


class FakeClient:
    async def send_many(self, items):
        sent.extend(items)
        return []


fas.get_notify_client = lambda: FakeClient()

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


async def _seed(session, challenge_id: int, risk: bool) -> None:
    today = today_str()
    for i in range(1, 8):
        d = shift_date(today, -i)
        for hh in (19, 20, 21):
            session.add(CheckIn(
                challenge_id=challenge_id, user_id="u1", day_number=1, status="completed",
                timestamp=datetime.strptime(f"{d} {hh:02d}:00", "%Y-%m-%d %H:%M"),
                date=d, value=3.0 if risk else 0.5, unit="根", target_value=8.0,
                goal_type="soft", direction="decrease", completion_pct=100.0,
            ))
    session.add(CheckIn(
        challenge_id=challenge_id, user_id="u1", day_number=1, status="completed",
        timestamp=datetime.strptime(f"{today} 18:00", "%Y-%m-%d %H:%M"),
        date=today, value=6.0 if risk else 0.5, unit="根", target_value=8.0,
        goal_type="soft", direction="decrease", completion_pct=100.0,
    ))
    await session.commit()


async def main() -> None:
    await init_db()
    repo = ChallengeRepository()
    async with async_session() as setup:
        await repo.create(setup, {
            "user_id": "u1", "title": "戒烟30天", "description": "", "category": "quit",
            "duration_days": 30, "start_date": shift_date(today_str(), -6),
            "end_date": shift_date(today_str(), 23), "status": "active",
            "ai_plan": "[]", "color": "#ef4444", "icon": "🚭",
            "task_type": "counter", "scene_template": "quit", "target_value": 8.0,
            "unit": "根", "direction": "decrease", "goal_type": "soft",
            "goal_rule": "fixed", "goal_mode": "ceiling",
        })
        await setup.commit()

    print("== 纯函数: 文案与聚合 ==")
    check("alert_text 优先 coach_nudge",
          fas.alert_text({"coach_nudge": "预计会超3", "risk_window_msg": "20点最难"}) == "预计会超3")
    check("alert_text 兜底 risk_window_msg",
          fas.alert_text({"coach_nudge": "", "risk_window_msg": "20点最难"}) == "20点最难")
    check("alert_text 都空返回空", fas.alert_text({}) == "")

    class _Ch:
        def __init__(self, t): self.title = t

    t1, c1 = fas._compose([(_Ch("戒烟30天"), {}, "预计会超3")])
    check("单挑战标题", t1 == "「戒烟30天」节奏提醒", t1)
    t2, c2 = fas._compose([(_Ch("戒烟"), {}, "a"), (_Ch("跑步"), {}, "b")])
    check("多挑战标题", t2 == "2 个挑战需要你留意", t2)

    print("== 高风险触发提醒 ==")
    async with async_session() as session:
        await _seed(session, 1, risk=True)
    sent.clear()
    await fas.send_forecast_alerts()
    check("触发1条提醒", len(sent) == 1, str(len(sent)))
    if sent:
        item = sent[0]
        check("标题含挑战名", "戒烟30天" in str(item.get("title", "")), str(item.get("title")))
        check("渠道 in_app+email", item.get("channels") == ["in_app", "email"], str(item.get("channels")))
        check("app_id 正确", item.get("app_id") == "challengePlanet", str(item.get("app_id")))
        check("优先级 3或4", int(item.get("priority", 0)) in (3, 4), str(item.get("priority")))

    print("== 同日去重 ==")
    sent.clear()
    await fas.send_forecast_alerts()
    check("同日不重复提醒", len(sent) == 0, str(len(sent)))

    print("== 低风险不打扰 ==")
    async with async_session() as session:
        from sqlalchemy import delete
        from app.models.checkin import AIInsight
        await session.execute(delete(CheckIn).where(CheckIn.challenge_id == 1))
        await session.execute(delete(AIInsight))
        await session.commit()
        await _seed(session, 1, risk=False)
    sent.clear()
    await fas.send_forecast_alerts()
    check("低风险不提醒", len(sent) == 0, str(len(sent)))

    print("\n=== 结果 ===")
    for f in failed:
        print("  FAILED:", f)
    print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
