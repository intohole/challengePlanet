# -*- coding: utf-8 -*-
# 减肥目标运动消耗 · 端到端集成测试
# 真实 FastAPI app + 临时 SQLite 库 + 真实 HTTP 序列化，
# 仅桩外部不可达依赖(LLM 估算/AI 反馈)。校验运动折算卡路里/净热量判定/额度抵扣/参数校验。
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

_tmp = tempfile.NamedTemporaryFile(suffix=".db", prefix="cp_sport_", delete=False)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmp.name
os.environ["SERVICE_TOKEN"] = "test-service-token"

import httpx  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.main import app  # noqa: E402
from app.db.database import async_session as test_session  # noqa: E402
from nexus import get_current_user_id_required  # noqa: E402

USER = "sport_e2e_user"

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
            "confidence": 0.7, "items": [{"name": "测试餐", "kcal": 1650}],
        }

    async def noop(*a, **k):
        return None

    AIService.estimate_diet_calories = fake_estimate
    AIService.estimate_diet_calories_from_photo = fake_estimate
    checkin.fill_ai_after_checkin = noop
    checkin.save_memory = noop
    checkin.evaluate_after_bad_mood_task = noop
    checkin.generate_weekly_report_task = noop


async def main() -> int:
    _patch_external()
    app.dependency_overrides[get_current_user_id_required] = lambda: USER

    from app.services.challenge_service import ChallengeService
    from app.services.diet_service import calc_daily_target
    from app.services.streak_service import shift_date, today_str

    cal = calc_daily_target("男", 30, 175, 80, 72, 2, 30)
    exp_target = float(cal["target_kcal"])

    async def _run() -> int:
        from app.db.database import init_db, run_migrations
        await init_db()
        await run_migrations()

        svc = ChallengeService()
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t",
                                     headers={"X-Service-Token": "test-service-token"}) as c:
            async with test_session() as s:
                ch = await svc.create_with_plan(
                    s, USER, "30天减重", "控制每日卡路里摄入科学减脂", "fitness", 30,
                    shift_date(today_str(), -1), [], task_type="diet",
                    gender="男", age=30, height_cm=175, weight_kg=80,
                    goal_weight=72, activity_level=2, unit="千卡",
                )
                other = await svc.create_with_plan(
                    s, USER, "读书", "", "learn", 10, shift_date(today_str(), -1), [],
                    task_type="binary", unit="次")
            cid, oid = ch.id, other.id
            print(f"\n创建饮食挑战 id={cid}, 目标摄入={exp_target}")

            print("\n== 1. 首餐打卡 ==")
            meal1 = round(exp_target * 0.6)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin",
                             json={"value": meal1, "reflection": "早餐：鸡蛋牛奶", "mood": "good"})
            check("首餐打卡 200", r.status_code == 200, str(r.status_code))
            check("首餐累计=本餐", abs(float(r.json()["today_total"]) - meal1) < 0.01, str(r.json()["today_total"]))

            print("\n== 2. 运动打卡折算卡路里(跑步30分钟·体重80kg) ==")
            expect_burn = round(9.8 * 80 * 30 / 60, 1)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin",
                             json={"value": 0, "sport_type": "running", "sport_minutes": 30})
            check("运动打卡 200", r.status_code == 200, str(r.status_code))
            js = r.json()
            check(f"折算消耗={expect_burn}", abs(float(js["checkin"]["calories"]) - expect_burn) < 0.01,
                  str(js["checkin"]["calories"]))
            check("运动不改摄入累计", abs(float(js["today_total"]) - meal1) < 0.01, str(js["today_total"]))
            check("运动记录默认文案", "跑步" in str(js["checkin"]["reflection"]), str(js["checkin"]["reflection"]))
            sport_id = int(js["checkin"]["id"])

            print("\n== 3. today 回传运动记录 ==")
            r = await c.get(f"/api/v1/challenges/{cid}/today")
            jt = r.json()
            sports = [x for x in jt["today_checkins"] if not x["value"] and x["calories"] > 0]
            check("today 含运动记录", len(sports) == 1 and abs(float(sports[0]["calories"]) - expect_burn) < 0.01,
                  str(jt["today_checkins"]))
            check("运动计入今日已打卡", jt["checked_in"] is True, str(jt["checked_in"]))

            print("\n== 4. 估算累计按净摄入(扣运动) ==")
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={"description": "晚餐一碗面"})
            je = r.json()
            check("净累计=摄入-运动", abs(float(je["today_intake"]) - (meal1 - expect_burn)) < 0.01,
                  str(je["today_intake"]))

            print("\n== 5. 再记一餐 · 净热量判定达标 ==")
            meal2 = round(exp_target * 0.65)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin",
                             json={"value": meal2, "reflection": "午餐：盒饭", "mood": "normal"})
            jc = r.json()
            net = meal1 + meal2 - expect_burn
            check("摄入累计不含运动", abs(float(jc["today_total"]) - (meal1 + meal2)) < 0.01, str(jc["today_total"]))
            check(f"净摄入{net}在目标±10% → 完成度100",
                  float(jc["checkin"]["completion_pct"]) == 100.0 and 0.9 <= net / exp_target <= 1.1,
                  f"pct={jc['checkin']['completion_pct']} net={net}")

            print("\n== 6. 参数校验 ==")
            r = await c.post(f"/api/v1/challenges/{cid}/checkin",
                             json={"value": 0, "sport_type": "moonwalk", "sport_minutes": 30})
            check("无效运动类型 400", r.status_code == 400, str(r.status_code))
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": 0})
            check("空记录 400", r.status_code == 400, str(r.status_code))

            print("\n== 7. 非 diet 挑战忽略运动字段 ==")
            r = await c.post(f"/api/v1/challenges/{oid}/checkin",
                             json={"value": 1, "sport_type": "running", "sport_minutes": 30})
            check("binary 打卡 200", r.status_code == 200, str(r.status_code))
            check("无运动折算", float(r.json()["checkin"]["calories"]) == 0.0, str(r.json()["checkin"]["calories"]))

            print("\n== 8. 撤销运动打卡 · 额度恢复 ==")
            r = await c.delete(f"/api/v1/challenges/{cid}/checkins/{sport_id}")
            check("撤销 200", r.status_code == 200, str(r.status_code))
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={"description": "加餐"})
            check("撤销后净累计恢复", abs(float(r.json()["today_intake"]) - (meal1 + meal2)) < 0.01,
                  str(r.json()["today_intake"]))

        return 0

    code = await _run()
    print(f"\n通过 {len(passed)} 项, 失败 {len(failed)} 项")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    return code if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
