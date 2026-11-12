#!/usr/bin/env python3
"""r27 回流重启引擎浏览器 E2E：重启卡渲染+接受动线+上限即时生效（真起服真浏览器）。

前置：tests/fe5_regression_env.py 已就绪（8610+stub 9535）。种子写环境库。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.environ.get("CP_DB", "/tmp/cp_fe5_regression.db")
BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def seed_gap(uid: str) -> int:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import app.models  # noqa: F401
    from app.core.datetime_utils import now_china
    from app.models.challenge import Challenge
    from app.models.checkin import CheckIn
    from app.services.streak_service import shift_date, today_str

    async def _seed() -> int:
        eng = create_async_engine("sqlite+aiosqlite:///" + DB)
        SM = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with SM() as s:
            today = today_str()
            ch = Challenge(
                user_id=uid, title="戒断挑战", category="quit", task_type="counter", unit="根",
                direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
                duration_days=66, status="active",
                ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
                ladder_adjust=json.dumps([{"day": 6, "shift": 2}]),
                target_value=12.0, ai_plan="[]", share_token="tr27br", color="#ef4444", icon="🚭",
                start_date=shift_date(today, -34), end_date=shift_date(today, 31),
            )
            s.add(ch)
            await s.flush()
            gap_start = shift_date(today, -27)
            for d, v in [(shift_date(gap_start, -2), 2.0), (gap_start, 5.0), (gap_start, 2.0)]:
                s.add(CheckIn(
                    challenge_id=ch.id, user_id=uid, date=d, value=v, day_number=1,
                    status="done", target_value=12.0, timestamp=now_china(),
                    unit="根", direction="decrease",
                ))
            await s.commit()
            cid = int(ch.id)
        await eng.dispose()
        return cid

    return asyncio.run(_seed())


def main() -> int:
    from playwright.sync_api import sync_playwright
    import jwt

    uid = "r27br" + str(int(time.time()))
    now = int(time.time())
    SECRET = "cp-fe5-regression-secret" * 2
    token = jwt.encode({"sub": uid, "exp": now + 7200}, SECRET, algorithm="HS256")
    cid = seed_gap(uid)
    check("种子：cap 阶梯+缺口 26 天", cid > 0)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.evaluate(
            """([t, uid]) => { localStorage.setItem('uc_access_token', t);
                 localStorage.setItem('cp_user_id', uid);
                 localStorage.setItem('cp_nickname', 'R27实验'); }""",
            [token, uid],
        )
        page.goto(BASE + "/", wait_until="domcontentloaded")

        page.wait_for_selector('[data-testid="restart-card"]', timeout=30000)
        check("回流第一眼重启卡（非 3 根任务卡）", True)
        hero = page.text_content('[data-testid="restart-card"]') or ""
        check("文案三件：太陡+上次守住+重新出发", "太陡" in hero and "重新出发" in hero, hero[:80])
        cap_now = page.text_content(".cp-ladder-daily-head") or ""
        check("任务卡今日上限 3（重锚前日历值）", " 3 " in " " + cap_now + " ", cap_now[:60])

        page.click('[data-testid="restart-accept"]')
        page.wait_for_selector('[data-testid="restart-card"]', state="detached", timeout=10000)
        check("接受后重启卡退场", True)
        page.wait_for_timeout(600)
        cap_after = page.text_content(".cp-ladder-daily-head") or ""
        check("任务卡今日上限即时变 7", " 7 " in " " + cap_after + " ", cap_after[:60])

        page.screenshot(path="/tmp/cp_r27_restart_accepted.png", full_page=False)
        browser.close()

    print(f"\n== r27 browser E2E: {len(passed)} passed / {len(failed)} failed ==")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
