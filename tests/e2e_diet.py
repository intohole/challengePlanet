# -*- coding: utf-8 -*-
# 体重控制打卡 · 端到端集成测试
# 真实 FastAPI app + 临时 SQLite 库 + 真实 HTTP 序列化，
# 仅桩外部不可达依赖(LLM 估算)。校验卡路里目标/达标判定/体重趋势/打卡闭环。
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", prefix="cp_diet_", delete=False)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmp.name
os.environ["SERVICE_TOKEN"] = "test-service-token"

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import async_session as test_session  # noqa: E402
from nexus import get_current_user_id_required  # noqa: E402

USER = "diet_e2e_user"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def _patch_external() -> None:
    import app.services.ai_service as ai
    import app.services.checkin_service as checkin
    from app.services.ai_service import AIService

    async def fake_estimate(self, description: str) -> dict:
        return {
            "total_kcal": 1650.0, "min_kcal": 1450.0, "max_kcal": 1850.0,
            "confidence": 0.7,
            "items": [
                {"name": "早餐鸡蛋", "kcal": 120},
                {"name": "午餐盒饭", "kcal": 780},
                {"name": "晚餐一碗面", "kcal": 560},
                {"name": "奶茶", "kcal": 190},
            ],
        }

    async def noop(*a, **k):
        return None

    AIService.estimate_diet_calories = fake_estimate
    checkin.fill_ai_after_checkin = noop
    checkin.save_memory = noop
    checkin.evaluate_after_bad_mood_task = noop
    checkin.generate_weekly_report_task = noop
    ai.get_llm_service.cache_clear() if hasattr(ai.get_llm_service, "cache_clear") else None


def calc_expected() -> float:
    from app.services.diet_service import calc_daily_target
    cal = calc_daily_target("男", 30, 175, 80, 72, 2, 30)
    return float(cal["target_kcal"])


def main() -> int:
    _patch_external()
    app.dependency_overrides[get_current_user_id_required] = lambda: USER

    from app.services.diet_service import calc_daily_target
    from app.services.challenge_service import ChallengeService

    cal = calc_daily_target("男", 30, 175, 80, 72, 2, 30)
    exp_target = float(cal["target_kcal"])
    exp_deficit = float(cal["deficit_kcal"])
    print(f"预期目标摄入 {exp_target} 千卡, 缺口 {exp_deficit} 千卡")

    async def _setup(svc: ChallengeService):
        async with test_session() as s:
            return await svc.create_with_plan(
                s, USER, "30天减重", "控制每日卡路里摄入科学减脂", "fitness", 30,
                "2026-08-25", [], task_type="diet",
                gender="男", age=30, height_cm=175, weight_kg=80,
                goal_weight=72, activity_level=2, unit="千卡",
            )

    async def _other(svc: ChallengeService):
        async with test_session() as s:
            return await svc.create_with_plan(
                s, USER, "读书", "", "learn", 10, "2026-08-25", [],
                task_type="binary", unit="次")

    async def _run() -> int:
        from app.db.database import init_db, run_migrations
        await init_db()
        await run_migrations()

        svc = ChallengeService()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t",
                                     headers={"X-Service-Token": "test-service-token"}) as c:
            ch = await _setup(svc)
            cid = ch.id
            print(f"\n创建饮食挑战 id={cid}, daily_calorie_target={ch.daily_calorie_target}")
            check("创建后写入卡路里目标", float(ch.daily_calorie_target or 0) == exp_target,
                  f"{ch.daily_calorie_target} != {exp_target}")

            print("\n== 1. 查询卡路里目标 ==")
            r = await c.get(f"/api/v1/challenges/{cid}/diet/target")
            check("target 返回 200", r.status_code == 200, str(r.status_code))
            jt = r.json()
            check("目标值一致", float(jt["target_kcal"]) == exp_target, str(jt))
            check("缺口一致", float(jt["deficit_kcal"]) == exp_deficit, str(jt))
            check("当前/目标体重回传", jt["current_weight"] == 80 and jt["goal_weight"] == 72, str(jt))

            print("\n== 2. LLM 估算当日摄入 ==")
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={"description": "早餐一个鸡蛋加牛奶，午餐盒饭，晚餐一碗面，还喝了杯奶茶"})
            check("estimate 返回 200", r.status_code == 200, str(r.status_code))
            je = r.json()
            check("总量 1650", abs(float(je["total_kcal"]) - 1650.0) < 0.01, str(je.get("total_kcal")))
            check("目标/缺口注入", float(je["target_kcal"]) == exp_target and float(je["deficit_kcal"]) == exp_deficit, str(je))
            check("4 个食物明细", isinstance(je["items"], list) and len(je["items"]) == 4, str(je.get("items")))
            expect_under_pct_e = round(1650.0 * 100.0 / exp_target, 1)
            check("摄入低于目标判定(under)", je["assessment"]["status"] == "under"
                  and abs(float(je["assessment"]["percent"]) - expect_under_pct_e) < 1.0,
                  str(je["assessment"]))

            print("\n== 3. 非饮食挑战不可估算 ==")
            other = await _other(svc)
            r = await c.post(f"/api/v1/challenges/{other.id}/diet/estimate", json={"description": "随便"})
            check("非饮食任务返回 400", r.status_code == 400, str(r.status_code))

            print("\n== 4. 记录体重 & 7日均值趋势 ==")
            r = await c.post(f"/api/v1/challenges/{cid}/weight", json={"weight_kg": 79.5})
            check("记录体重 200", r.status_code == 200, str(r.status_code))
            check("新增非更新", r.json().get("updated") is False, str(r.json()))
            r = await c.post(f"/api/v1/challenges/{cid}/weight", json={"weight_kg": 79.2, "date": "2026-08-24"})
            check("带日期新增", r.status_code == 200, str(r.status_code))
            now = await c.get(f"/api/v1/challenges/{cid}/weight/trend")
            check("trend 返回 200", now.status_code == 200, str(now.status_code))
            jw = now.json()
            check("两条记录", jw["count"] == 2, str(jw["count"]))
            latest = jw["latest"]
            check("最新=今日79.5", abs(float(latest["weight_kg"]) - 79.5) < 0.01, str(latest))
            check("7日均值=两条均值", abs(float(latest["avg7"]) - round((79.2 + 79.5) / 2, 2)) < 0.01, str(latest["avg7"]))
            check("较首日=+0.3", abs(float(latest["delta"]) - 0.3) < 0.01, str(latest["delta"]))

            print("\n== 5. 饮食打卡 · 达标判定 ==")
            over_value = round(exp_target * 0.6)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": over_value, "reflection": "今天吃少了", "mood": "good"})
            check("摄入偏少打卡 200", r.status_code == 200, str(r.status_code))
            jc = r.json()
            pct_under = jc["checkin"]["completion_pct"]
            expect_under_pct = sorted([30.0, round(over_value * 100.0 / exp_target, 1), 90.0])[1]
            check(f"偏少完成度={expect_under_pct}", abs(pct_under - expect_under_pct) < 1.0, str(pct_under))

            on_value = round(exp_target)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": on_value, "reflection": "达标", "mood": "good"})
            jc = r.json()
            check("达标(±10%)完成度=100", float(jc["checkin"]["completion_pct"]) == 100.0, str(jc["checkin"]["completion_pct"]))

            hi_value = round(exp_target * 1.8)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": hi_value, "reflection": "吃多了", "mood": "bad"})
            jc = r.json()
            pc = float(jc["checkin"]["completion_pct"])
            expect_hi = sorted([30.0, (2 - 1.8) * 100, 90.0])[1]
            check(f"偏高完成度=20→30clamp={expect_hi}", abs(pc - expect_hi) < 1.0, str(pc))
        return 1 if failed else 0

    rc = asyncio.run(_run())
    app.dependency_overrides.clear()
    print("\n===== 汇总 =====")
    print(f"通过 {len(passed)} 项, 失败 {len(failed)} 项")
    for name, d in failed:
        print(f"  FAILED: {name} :: {d}")
    try:
        os.remove(_tmp.name)
    except OSError:
        pass
    return rc


if __name__ == "__main__":
    raise SystemExit(main())