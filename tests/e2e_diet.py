# -*- coding: utf-8 -*-
# 体重控制打卡 · 端到端集成测试
# 真实 FastAPI app + 临时 SQLite 库 + 真实 HTTP 序列化，
# 仅桩外部不可达依赖(LLM 估算/视觉识别)。校验卡路里目标/拍照识别/每餐累计/体重趋势/打卡闭环。
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

    async def fake_photo(self, image: str) -> dict:
        if not image.startswith("data:image/"):
            return {"total_kcal": 0, "min_kcal": 0, "max_kcal": 0, "confidence": 0, "items": []}
        return {
            "total_kcal": 520.0, "min_kcal": 460.0, "max_kcal": 600.0,
            "confidence": 0.6,
            "items": [
                {"name": "米饭一小碗", "kcal": 180},
                {"name": "宫保鸡丁", "kcal": 260},
                {"name": "青菜", "kcal": 80},
            ],
        }

    async def noop(*a, **k):
        return None

    AIService.estimate_diet_calories = fake_estimate
    AIService.estimate_diet_calories_from_photo = fake_photo
    checkin.fill_ai_after_checkin = noop
    checkin.save_memory = noop
    checkin.evaluate_after_bad_mood_task = noop
    checkin.generate_weekly_report_task = noop
    ai.get_llm_service.cache_clear() if hasattr(ai.get_llm_service, "cache_clear") else None


def main() -> int:
    _patch_external()
    app.dependency_overrides[get_current_user_id_required] = lambda: USER

    from app.services.diet_service import calc_daily_target
    from app.services.challenge_service import ChallengeService
    from app.services.streak_service import shift_date, today_str

    cal = calc_daily_target("男", 30, 175, 80, 72, 2, 30)
    exp_target = float(cal["target_kcal"])
    exp_deficit = float(cal["deficit_kcal"])
    print(f"预期目标摄入 {exp_target} 千卡, 缺口 {exp_deficit} 千卡")

    async def _setup(svc: ChallengeService):
        async with test_session() as s:
            return await svc.create_with_plan(
                s, USER, "30天减重", "控制每日卡路里摄入科学减脂", "fitness", 30,
                shift_date(today_str(), -1), [], task_type="diet",
                gender="男", age=30, height_cm=175, weight_kg=80,
                goal_weight=72, activity_level=2, unit="千卡",
            )

    async def _other(svc: ChallengeService):
        async with test_session() as s:
            return await svc.create_with_plan(
                s, USER, "读书", "", "learn", 10, shift_date(today_str(), -1), [],
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

            print("\n== 2. 描述估算(今日首餐) ==")
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={"description": "早餐一个鸡蛋加牛奶，午餐盒饭，晚餐一碗面，还喝了杯奶茶"})
            check("estimate 返回 200", r.status_code == 200, str(r.status_code))
            je = r.json()
            check("总量 1650", abs(float(je["total_kcal"]) - 1650.0) < 0.01, str(je.get("total_kcal")))
            check("目标/缺口注入", float(je["target_kcal"]) == exp_target and float(je["deficit_kcal"]) == exp_deficit, str(je))
            check("4 个食物明细", isinstance(je["items"], list) and len(je["items"]) == 4, str(je.get("items")))
            check("尚无今日累计", float(je["today_intake"]) == 0.0, str(je.get("today_intake")))
            expect_under_pct_e = round(1650.0 * 100.0 / exp_target, 1)
            check("摄入低于目标判定(under)", je["assessment"]["status"] == "under"
                  and abs(float(je["assessment"]["percent"]) - expect_under_pct_e) < 1.0,
                  str(je["assessment"]))

            print("\n== 3. 拍照识别(餐食照片) ==")
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate",
                             json={"image": "data:image/jpeg;base64,/9j/AAAA"})
            check("拍照 estimate 返回 200", r.status_code == 200, str(r.status_code))
            jp = r.json()
            check("这一餐 520 千卡", abs(float(jp["meal_kcal"]) - 520.0) < 0.01, str(jp.get("meal_kcal")))
            check("识别出 3 个食物", len(jp["items"]) == 3, str(jp.get("items")))
            check("拍照置信度回传", float(jp["confidence"]) == 0.6, str(jp.get("confidence")))

            print("\n== 4. 参数校验与场景校验 ==")
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={})
            check("空描述空照片 400", r.status_code == 400, str(r.status_code))
            r = await c.post(f"/api/v1/challenges/{cid}/diet/estimate", json={"image": "x" * 6_000_001})
            check("超大照片 400", r.status_code == 400, str(r.status_code))
            other = await _other(svc)
            r = await c.post(f"/api/v1/challenges/{other.id}/diet/estimate", json={"description": "随便"})
            check("非饮食任务返回 400", r.status_code == 400, str(r.status_code))
            r = await c.get(f"/api/v1/challenges/{cid}/today")
            check("饮食场景不做节奏预测", r.json()["forecast"]["enabled"] is False, str(r.json().get("forecast")))

            print("\n== 5. 记录体重 & 7日均值趋势 ==")
            r = await c.post(f"/api/v1/challenges/{cid}/weight", json={"weight_kg": 79.5})
            check("记录体重 200", r.status_code == 200, str(r.status_code))
            check("新增非更新", r.json().get("updated") is False, str(r.json()))
            r = await c.post(f"/api/v1/challenges/{cid}/weight", json={"weight_kg": 79.2, "date": shift_date(today_str(), -1)})
            check("带日期新增", r.status_code == 200, str(r.status_code))
            now = await c.get(f"/api/v1/challenges/{cid}/weight/trend")
            check("trend 返回 200", now.status_code == 200, str(now.status_code))
            jw = now.json()
            check("两条记录", jw["count"] == 2, str(jw["count"]))
            latest = jw["latest"]
            check("最新=今日79.5", abs(float(latest["weight_kg"]) - 79.5) < 0.01, str(latest))
            check("7日均值=两条均值", abs(float(latest["avg7"]) - round((79.2 + 79.5) / 2, 2)) < 0.01, str(latest["avg7"]))
            check("较首日=+0.3", abs(float(latest["delta"]) - 0.3) < 0.01, str(latest["delta"]))

            print("\n== 6. 每餐一笔 · 累计评估 ==")
            meal1 = round(exp_target * 0.6)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": meal1, "reflection": "早餐：鸡蛋牛奶", "mood": "good"})
            check("第一餐打卡 200", r.status_code == 200, str(r.status_code))
            jc = r.json()
            expect_pct = sorted([30.0, round(meal1 * 100.0 / exp_target, 1), 90.0])[1]
            check(f"第一餐(累计{meal1})完成度={expect_pct}", abs(float(jc["checkin"]["completion_pct"]) - expect_pct) < 1.0, str(jc["checkin"]["completion_pct"]))
            check("第一餐累计=本餐", abs(float(jc["today_total"]) - meal1) < 0.01, str(jc["today_total"]))

            meal2 = round(exp_target * 0.5)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": meal2, "reflection": "午餐：盒饭", "mood": "normal"})
            jc = r.json()
            check("第二餐累计=两餐之和", abs(float(jc["today_total"]) - (meal1 + meal2)) < 0.01, str(jc["today_total"]))
            check("累计落在目标±10% 完成度=100", float(jc["checkin"]["completion_pct"]) == 100.0, str(jc["checkin"]["completion_pct"]))
            check("多餐不重放", jc["already_checked"] is False, str(jc["already_checked"]))

            meal3 = round(exp_target * 0.7)
            r = await c.post(f"/api/v1/challenges/{cid}/checkin", json={"value": meal3, "reflection": "晚餐：面条+奶茶", "mood": "bad"})
            jc = r.json()
            total = meal1 + meal2 + meal3
            ratio = total / exp_target
            expect_hi = sorted([30.0, (2 - ratio) * 100, 90.0])[1]
            check(f"累计偏高完成度={expect_hi}", abs(float(jc["checkin"]["completion_pct"]) - expect_hi) < 1.0, str(jc["checkin"]["completion_pct"]))
            check("每餐均为新记录", jc["already_checked"] is False, str(jc["already_checked"]))

            print("\n== 7. 今日记录与撤销 ==")
            r = await c.get(f"/api/v1/challenges/{cid}/today")
            jt = r.json()
            check("今日三笔都在", len(jt["today_checkins"]) == 3, str(len(jt.get("today_checkins", []))))
            check("今日累计回传", abs(float(jt["today_total"]) - total) < 0.01, str(jt["today_total"]))
            last_id = jt["today_checkins"][-1]["id"]
            r = await c.delete(f"/api/v1/challenges/{cid}/checkins/{last_id}")
            check("撤销一笔 200", r.status_code == 200, str(r.status_code))
            r = await c.get(f"/api/v1/challenges/{cid}/today")
            check("撤销后累计减少", abs(float(r.json()["today_total"]) - (meal1 + meal2)) < 0.01, str(r.json()["today_total"]))
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