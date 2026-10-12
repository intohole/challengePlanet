#!/usr/bin/env python3
"""r19 浏览器冒烟：absence 回归卡渲染/换挡入口/零 JS 错误（本地 8610 真库造失踪场景）"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8610"
API = BASE + "/api/v1"
SPA = BASE + "/"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "out", "r19_shots")
os.makedirs(OUT, exist_ok=True)

USER = "cp_r19_br_" + str(int(time.time()))
PWD = "CpR19#x2026"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method: str, path: str, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def shift(days_ago: int) -> str:
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def make_plan(days: int) -> list[dict]:
    return [
        {"day": i + 1, "title": f"r19 第{i+1}天", "description": "E2E", "tip": "",
         "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
        for i in range(days)
    ]


async def seed_day(challenge_id: int, user_id: str, date: str, value: float) -> None:
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
            "timestamp": __import__("datetime").datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(ch.unit),
            "target_value": float(daily_target(ch, day_number)),
            "goal_type": str(ch.goal_type), "direction": str(ch.direction),
            "completion_pct": 100.0,
        })
        await session.commit()


async def cleanup(challenge_ids: list[int]) -> None:
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


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    check("注册拿到token", bool(token) and bool(uid), str(st)[:100])

    start = shift(4)
    ch = api("POST", "/challenges/confirm", {
        "title": "r19浏览器失踪阶梯", "category": "quit", "duration_days": 40,
        "start_date": start, "description": "E2E absence card", "plan": make_plan(40),
        "source": "manual", "task_type": "counter", "target_value": 15.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    cid = int(ch["id"])
    asyncio.run(seed_day(cid, uid, start, 15.0))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        console_errs: list[str] = []
        bad_urls: list[str] = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))
        page.on("response", lambda r: bad_urls.append(r.url) if r.status >= 400 else None)

        page.goto(SPA, wait_until="networkidle")
        page.wait_for_timeout(1500)
        app_html = page.evaluate("() => document.getElementById('app') ? document.getElementById('app').innerHTML.length : 0")
        check("SPA渲染非空", app_html > 1000, str(app_html))

        card = page.query_selector('[data-testid="absence-card"]')
        check("absence回归卡渲染", card is not None, "card not found")
        if card:
            txt = card.inner_text()
            check("卡文案含天数", "3 天没见了" in txt, txt[:100])
            check("卡文案含记一笔守住", "记一笔就算守住" in txt, txt[:120])
            check("avoided=0时省略少抽句", "已少抽的" not in txt, txt[:120])
            check("卡含换挡按钮(suggest_adjust)", card.query_selector(".cp-absence-log-btn + .cp-btn-primary, button.cp-btn-primary") is not None, txt[:120])
        page.screenshot(path=os.path.join(OUT, "absence_card_light.png"))
        page.emulate_media(color_scheme="dark")
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(OUT, "absence_card_dark.png"))
        page.emulate_media(color_scheme="light")

        shift_btns = page.query_selector_all('[data-testid="absence-card"] button')
        if shift_btns:
            shift_btns[-1].click()
            page.wait_for_timeout(400)
            gone = page.query_selector('[data-testid="absence-card"]')
            check("先看看可关闭卡片", gone is None, "card still visible")
        page.screenshot(path=os.path.join(OUT, "absence_dismissed.png"))

        real_404 = [u for u in bad_urls if "uc-api" not in u and "/api/auth/config" not in u and "favicon" not in u]
        check("零资源错误(排除本地nginx差异)", len(real_404) == 0, str(real_404[:3]))
        js_exceptions = [e for e in console_errs if "Failed to load resource" not in e]
        check("零JS异常", len(js_exceptions) == 0, str(js_exceptions[:3]))
        browser.close()

    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail[:140]}")
    asyncio.run(cleanup([cid]))
    print("cleanup done")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
