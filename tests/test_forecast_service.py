#!/usr/bin/env python3
"""集成测试: ForecastService 回测校准闭环(预测落库→次日比对→bias修正)"""
from __future__ import annotations

import os
import sys
import tempfile

tmpdir = tempfile.mkdtemp(prefix="cp_forecast_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmpdir}/test.db"
sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

import asyncio
import json
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.datetime_utils import now_china
from app.db.database import async_session, init_db
from app.models.checkin import AIInsight, CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.services.forecast_service import ForecastService
from app.services.streak_service import shift_date, today_str


class FakeCh:
    def __init__(self, cid=1, uid="u1"):
        self.id = cid
        self.user_id = uid
        self.direction = "decrease"
        self.unit = "根"
        self.goal_rule = "fixed"
        self.target_value = 8.0
        self.duration_days = 30
        self.ladder_goal = 0.0
        self.ladder_start = 0.0


passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


async def main() -> None:
    await init_db()
    challenge = FakeCh()
    repo = ChallengeRepository()
    async with async_session() as setup:
        await repo.create(setup, {
            "user_id": "u1", "title": "戒烟", "description": "", "category": "quit",
            "duration_days": 30, "start_date": shift_date(today_str(), -5),
            "end_date": shift_date(today_str(), 24), "status": "active",
            "ai_plan": "[]", "color": "#ef4444", "icon": "🚭",
            "task_type": "counter", "scene_template": "quit", "target_value": 8.0,
            "unit": "根", "direction": "decrease", "goal_type": "soft",
            "goal_rule": "fixed", "goal_mode": "ceiling",
        })
        await setup.commit()
    async with async_session() as session:
        yesterday = shift_date(today_str(), -1)
        ts = datetime.strptime(yesterday + " 09:00", "%Y-%m-%d %H:%M")
        checkins = [
            CheckIn(challenge_id=1, user_id="u1", day_number=4, status="completed",
                    timestamp=ts, date=yesterday, value=2.0, unit="根",
                    target_value=8.0, goal_type="soft", direction="decrease",
                    completion_pct=100.0),
            CheckIn(challenge_id=1, user_id="u1", day_number=4, status="completed",
                    timestamp=ts + timedelta(hours=2), date=yesterday, value=3.0, unit="根",
                    target_value=8.0, goal_type="soft", direction="decrease",
                    completion_pct=100.0),
        ]
        session.add_all(checkins)
        await session.commit()

        forecast_service = ForecastService()
        today = today_str()
        now = now_china()
        hour = now.hour
        today_total = 2.0
        today_target = 8.0

        fc = await forecast_service.build(
            session, challenge, today_total, today_target, hour, day_number=5,
        )
        check("预测启用", bool(fc["enabled"]), str(fc))
        check("预测单值(无区间)", "projected_low" not in fc and fc["projected"] > 0, str(fc))
        check("预测带置信度", fc["confidence"] > 0, str(fc))
        check("预测带依据", bool(fc["basis"]), str(fc))

        rows = (await session.execute(select(AIInsight))).scalars().all()
        forecast_rows = [r for r in rows if r.insight_type == "forecast"]
        check("预测快照已落库", len(forecast_rows) >= 1, str(len(forecast_rows)))

        fc_again = await forecast_service.build(
            session, challenge, today_total, today_target, hour, day_number=5,
        )
        rows2 = (await session.execute(select(AIInsight))).scalars().all()
        forecast_rows2 = [r for r in rows2 if r.insight_type == "forecast"]
        check("同一天不重复落库", len(forecast_rows2) == len(forecast_rows), f"{len(forecast_rows2)} vs {len(forecast_rows)}")
        check("二次预测数值一致", fc_again["projected"] == fc["projected"], f"{fc_again['projected']} vs {fc['projected']}")

        ts2 = datetime.strptime(today + " 09:00", "%Y-%m-%d %H:%M")
        session.add(CheckIn(challenge_id=1, user_id="u1", day_number=5, status="completed",
                            timestamp=ts2, date=today, value=2.0, unit="根",
                            target_value=8.0, goal_type="soft", direction="decrease",
                            completion_pct=100.0))
        await session.commit()
        check("今日打卡后 预测仍可用", True)

    print("== 回测校准: 模拟昨天预测5根 实际3根 -> 今日预测下调 ==")
    async with async_session() as session:
        from sqlalchemy import delete
        await session.execute(delete(AIInsight).where(AIInsight.insight_type == "forecast"))
        await session.execute(delete(CheckIn).where(CheckIn.challenge_id == 1))
        await session.commit()
        forecast_service = ForecastService()
        now = now_china()
        hour = now.hour
        yesterday = shift_date(today_str(), -1)
        session.add(AIInsight(challenge_id=1, user_id="u1", insight_type="forecast",
                              content=json.dumps({"date": yesterday, "enabled": True,
                                                  "projected": 5.0, "basis": "", "confidence": 0.6})))
        session.add(CheckIn(challenge_id=1, user_id="u1", day_number=4, status="completed",
                            timestamp=datetime.strptime(yesterday + " 10:00", "%Y-%m-%d %H:%M"),
                            date=yesterday, value=3.0, unit="根",
                            target_value=8.0, goal_type="soft", direction="decrease",
                            completion_pct=100.0))
        await session.commit()
        bias = await forecast_service._calibration_bias(session, 1)
        check("昨日预测5实际3 bias=-1", bias == -1.0, str(bias))
        base = forecast_service._nudge.evaluate(FakeCh(), 2.0, 8.0, hour, day_number=6)
        check("无校准基准 projected>0", base["projected"] > 0, str(base["projected"]))
        fc = await forecast_service.build(session, FakeCh(), 2.0, 8.0, hour, day_number=6)
        check("预测带校准标记", bool(fc["calibrated"]), str(fc))
        check("预测已下调", fc["projected"] < base["projected"], f"{fc['projected']} vs {base['projected']}")

    print("== 情境维度纳入预测 ==")
    async with async_session() as session:
        from sqlalchemy import delete
        await session.execute(delete(AIInsight))
        await session.execute(delete(CheckIn).where(CheckIn.challenge_id == 1))
        await session.commit()
        base_day = shift_date(today_str(), -8)
        filler_hours = (8, 12, 19, 22)
        for i in range(7):
            d = shift_date(base_day, i)
            for hh in filler_hours:
                session.add(CheckIn(challenge_id=1, user_id="u1", day_number=1, status="completed",
                                    timestamp=datetime.strptime(f"{d} {hh:02d}:00", "%Y-%m-%d %H:%M"),
                                    date=d, value=0.5, unit="根", target_value=8.0,
                                    goal_type="soft", direction="decrease", completion_pct=100.0,
                                    context_tag=""))
        ctx_by_day = ["social"] * 3 + ["home"] * 2 + ["work"] * 2
        ctx_val = {"social": 3.0, "home": 1.0, "work": 1.0}
        for i, tag in enumerate(ctx_by_day):
            d = shift_date(base_day, i)
            for hh in (20, 21):
                session.add(CheckIn(challenge_id=1, user_id="u1", day_number=1, status="completed",
                                    timestamp=datetime.strptime(f"{d} {hh:02d}:00", "%Y-%m-%d %H:%M"),
                                    date=d, value=ctx_val[tag], unit="根", target_value=8.0,
                                    goal_type="soft", direction="decrease", completion_pct=100.0,
                                    context_tag=tag))
        await session.commit()
        fc = await ForecastService().build(session, FakeCh(), 2.0, 8.0, 9, day_number=6)
        check("情境: 风险窗口已识别", fc.get("risk_window") == "20:00-21:00", str(fc.get("risk_window")))
        check("情境: 风险窗口主场景=社交", fc.get("risk_window_context") == "社交", str(fc.get("risk_window_context")))
        check("情境: 窗口文案含场景", "社交" in str(fc.get("risk_window_msg", "")), str(fc.get("risk_window_msg")))
        check("情境: 条件模式已生成", "倍" in str(fc.get("context_pattern", "")), str(fc.get("context_pattern")))

    print("\n=== 结果 ===")
    for f in failed:
        print("  FAILED:", f)
    print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
