#!/usr/bin/env python3
"""集成测试: ForecastService 预测编排(取数→预测→情境附加) + 场景门禁 + 静默门槛"""
from __future__ import annotations

import os
import sys
import tempfile

tmpdir = tempfile.mkdtemp(prefix="cp_forecast_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmpdir}/test.db"
sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from app.core.datetime_utils import now_china
from app.db.database import async_session, init_db
from app.models.checkin import AIInsight, CheckIn
from app.repositories.challenge_repository import ChallengeRepository
from app.services.forecast_scope import supports_forecast
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
        self.task_type = "counter"
        self.decompose_mode = "none"


class GateCh:
    def __init__(self, task_type="counter", unit="根", decompose_mode="none"):
        self.task_type = task_type
        self.unit = unit
        self.decompose_mode = decompose_mode


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

    print("== 预测编排: 取数→预测→依据 ==")
    async with async_session() as session:
        yesterday = shift_date(today_str(), -1)
        today = today_str()
        ts = datetime.strptime(yesterday + " 09:00", "%Y-%m-%d %H:%M")
        session.add_all([
            CheckIn(challenge_id=1, user_id="u1", day_number=4, status="completed",
                    timestamp=ts, date=yesterday, value=2.0, unit="根",
                    target_value=8.0, goal_type="soft", direction="decrease",
                    completion_pct=100.0),
            CheckIn(challenge_id=1, user_id="u1", day_number=4, status="completed",
                    timestamp=ts + timedelta(hours=2), date=yesterday, value=3.0, unit="根",
                    target_value=8.0, goal_type="soft", direction="decrease",
                    completion_pct=100.0),
            CheckIn(challenge_id=1, user_id="u1", day_number=5, status="completed",
                    timestamp=datetime.strptime(today + " 09:30", "%Y-%m-%d %H:%M"),
                    date=today, value=2.0, unit="根", target_value=8.0,
                    goal_type="soft", direction="decrease", completion_pct=100.0),
            CheckIn(challenge_id=1, user_id="u1", day_number=5, status="completed",
                    timestamp=datetime.strptime(today + " 10:20", "%Y-%m-%d %H:%M"),
                    date=today, value=2.0, unit="根", target_value=8.0,
                    goal_type="soft", direction="decrease", completion_pct=100.0),
        ])
        await session.commit()

        forecast_service = ForecastService()
        fc = await forecast_service.build(
            session, challenge, 4.0, 8.0, 10, day_number=5,
        )
        check("预测启用", bool(fc["enabled"]), str(fc))
        check("预测单值(无区间)", "projected_low" not in fc and fc["projected"] > 0, str(fc))
        check("预测带置信度", fc["confidence"] > 0, str(fc))
        check("预测带依据", bool(fc["basis"]), str(fc))
        check("今日两条记录 非静默", fc["quiet"] is False, str(fc))
        check("预测不带校准标记", "calibrated" not in fc, str(fc))

        rows = (await session.execute(select(AIInsight))).scalars().all()
        check("不再写预测快照", not [r for r in rows if r.insight_type == "forecast"], "forecast snapshot exists")

        fc_night = await forecast_service.build(session, challenge, 4.0, 8.0, 3, day_number=5)
        check("凌晨静默", fc_night["quiet"] is True and fc_night["projected"] == 0.0, str(fc_night))

    print("== 场景门禁: 哪些场景需要预测 ==")
    check("counter 启用", supports_forecast(GateCh("counter", "根")) is True)
    check("timer 时长 启用", supports_forecast(GateCh("timer", "分钟")) is True)
    check("timer 按时点 不启用", supports_forecast(GateCh("timer", "点")) is False)
    check("binary 不启用", supports_forecast(GateCh("binary", "次")) is False)
    check("text 不启用", supports_forecast(GateCh("text", "篇")) is False)
    check("word 不启用", supports_forecast(GateCh("word", "词")) is False)
    check("recite 不启用", supports_forecast(GateCh("recite", "首")) is False)
    check("diet 不启用", supports_forecast(GateCh("diet", "千卡")) is False)
    check("step 不启用", supports_forecast(GateCh("step", "项")) is False)
    check("time_slot 不启用", supports_forecast(GateCh("counter", "组", "time_slot")) is False)
    async with async_session() as session:
        binary_fc = await ForecastService().build(session, GateCh("binary", "次"), 1.0, 1.0, 10)
        check("门禁外场景 预测直接禁用", binary_fc["enabled"] is False, str(binary_fc))

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