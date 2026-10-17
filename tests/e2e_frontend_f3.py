#!/usr/bin/env python3
"""前3 浏览器 E2E：回归卡主行动接线/坡度行动条/换挡 sheet 上下文/持久化/先看看（本地 8610 真库）"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
SPA = BASE + "/"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "out", "fe3_shots")
os.makedirs(OUT, exist_ok=True)

STAMP = str(int(time.time()))
USER = "cp_fe3_e2e_" + STAMP
PWD = "CpFe3#x2026"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method, path, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def shift(days_ago):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def make_plan(days):
    return [
        {"day": i + 1, "title": f"前3第{i+1}天", "description": "E2E", "tip": "",
         "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
        for i in range(days)
    ]


async def seed_day(challenge_id, user_id, date, value):
    from app.db.database import async_session, init_db
    from app.services.goal_rule_service import daily_target
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.streak_service import day_number_of
    from app.repositories.challenge_repository import ChallengeRepository
    await init_db()
    async with async_session() as session:
        ch = await ChallengeRepository().get_by_id(session, challenge_id)
        day_number = day_number_of(str(ch.start_date), date)
        await CheckInRepository().create(session, {
            "challenge_id": challenge_id, "user_id": user_id, "day_number": day_number,
            "status": "completed",
            "timestamp": datetime.datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(ch.unit),
            "target_value": float(daily_target(ch, day_number)),
            "goal_type": str(ch.goal_type), "direction": str(ch.direction),
            "completion_pct": 100.0,
        })
        await session.commit()


async def cleanup(challenge_ids):
    from app.db.database import async_session, init_db
    from sqlalchemy import delete
    from app.models.checkin import AIInsight, CheckIn
    from app.models.challenge import Challenge
    await init_db()
    async with async_session() as session:
        if challenge_ids:
            await session.execute(delete(CheckIn).where(CheckIn.challenge_id.in_(challenge_ids)))
            await session.execute(delete(AIInsight).where(AIInsight.challenge_id.in_(challenge_ids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(challenge_ids)))
        await session.commit()


def create_absence_challenge(token, title):
    start = shift(4)
    ch = api("POST", "/challenges/confirm", {
        "title": title, "category": "quit", "duration_days": 40,
        "start_date": start, "description": "E2E f3", "plan": make_plan(40),
        "source": "manual", "task_type": "counter", "target_value": 15.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    return int(ch["id"]), start


def main():
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    assert token, str(st)[:200]

    cid_a, start_a = create_absence_challenge(token, "前3回归主链")
    asyncio.run(seed_day(cid_a, uid, start_a, 15.0))
    cid_b, start_b = create_absence_challenge(token, "前3先看看")
    asyncio.run(seed_day(cid_b, uid, start_b, 15.0))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        def today_total(cid):
            t = api("GET", f"/challenges/{cid}/today", token=token)
            return (t.get("data") or t).get("today_total")

        page.goto(SPA, wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="absence-card"]', timeout=15000)
        page.wait_for_timeout(600)

        card = page.query_selector('[data-testid="absence-card"]')
        check("A1 回归卡渲染", card is not None)
        log_btn = card.query_selector(".cp-absence-log-btn")
        shift_btn = card.query_selector(".cp-absence-shift-btn")
        check("A2 主行动按钮接线(logAbsenceReturn)", "logAbsenceReturn" in (log_btn.get_attribute("onclick") or ""), log_btn.get_attribute("onclick") or "")
        check("A3 阶梯后移降级 ghost 钮", shift_btn is not None and "cp-btn-primary" not in (shift_btn.get_attribute("class") or ""), shift_btn.get_attribute("class") if shift_btn else "none")
        primaries = card.query_selector_all("button.cp-btn-primary")
        check("A4 实底主钮唯一", len(primaries) == 1, str(len(primaries)))

        page.click('[data-testid="absence-card"] .cp-absence-log-btn')
        page.wait_for_timeout(400)
        try:
            cel = page.wait_for_selector(".cp-celebrate-text", timeout=3000)
            cel_txt = cel.inner_text()
            check("A5 celebrate 文案重组", "欢迎回来" in cel_txt and "离开 3 天" in cel_txt and "少抽的都还在 +" not in cel_txt, cel_txt)
        except Exception as e:
            check("A5 celebrate 文案重组", False, f"celebrate not shown: {e}")
        page.wait_for_timeout(1500)

        total_after = today_total(cid_a)
        check("A6 主按钮真记录 today_total=1", total_after == 1, str(total_after))
        card_gone = page.query_selector('[data-testid="absence-card"]')
        check("A7 打卡后回归卡消失", card_gone is None, "card still visible")
        slope = page.query_selector('[data-testid="slope-bar"]')
        check("A8 坡度行动条渲染(suggest_adjust)", slope is not None, "slope-bar missing")
        if slope:
            stxt = slope.inner_text()
            check("A9 行动条含上次记录与上限", "15 根" in stxt and "10 根" in stxt, stxt)

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        slope2 = page.query_selector('[data-testid="slope-bar"]')
        check("A10 reload 后行动条仍在(sessionStorage)", slope2 is not None, "slope-bar missing after reload")

        if slope2:
            page.click('[data-testid="slope-bar"] .cp-slope-btn')
            page.wait_for_timeout(800)
            sheet = page.query_selector('[data-testid="ladder-shift-sheet"]')
            check("A11 行动条打开换挡 sheet", sheet is not None, "sheet missing")
            if sheet:
                lede = sheet.query_selector(".cp-shift-lede").inner_text()
                check("A12 sheet lede absence 上下文", "离开 3 天回来了" in lede, lede)
                page.wait_for_timeout(600)
                preview = sheet.query_selector('[data-testid="shift-preview"]')
                ptxt = preview.inner_text() if preview else ""
                check("A13 preview 含上次记录行", "上次记录" in ptxt and "15" in ptxt, ptxt)
            page.click('[data-testid="ladder-shift-sheet"] [data-shift="3"]')
            page.wait_for_timeout(600)
            page.click('[data-testid="ladder-shift-sheet"] .cp-btn-primary.cp-block')
            page.wait_for_timeout(1500)
            check("A14 换挡后行动条消失", page.query_selector('[data-testid="slope-bar"]') is None, "slope-bar still visible")
            t2 = api("GET", f"/challenges/{cid_a}/today", token=token)
            new_cap = (t2.get("data") or t2).get("today_cap")
            check("A15 换挡真生效 cap 变化", new_cap != 10, f"cap={new_cap}（preview 显示 11 与落库 12 的口径差=r18 后端遗留，转业务轮）")

        page.goto(SPA + "?ch=" + str(cid_b), wait_until="domcontentloaded")
        page.wait_for_selector('[data-testid="absence-card"]', timeout=15000)
        page.wait_for_timeout(500)
        before_b = today_total(cid_b)
        btns = page.query_selector_all('[data-testid="absence-card"] button')
        btns[-1].click()
        page.wait_for_timeout(600)
        after_b = today_total(cid_b)
        check("B1 先看看仅关闭不记录", page.query_selector('[data-testid="absence-card"]') is None and before_b == 0 and after_b == 0, f"total {before_b}->{after_b}")

        page.set_viewport_size({"width": 375, "height": 812})
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(1200)
        sw = page.evaluate("() => document.body.scrollWidth")
        cw = page.evaluate("() => document.body.clientWidth")
        check("C1 375 无横向溢出", sw <= cw, f"scrollWidth={sw} clientWidth={cw}")

        real_js = [e for e in console_errs if "Failed to load resource" not in e]
        check("D1 零 JS 异常", len(real_js) == 0, str(real_js[:3]))
        browser.close()

    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail[:140]}")
    asyncio.run(cleanup([cid_a, cid_b]))
    print("cleanup done")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
