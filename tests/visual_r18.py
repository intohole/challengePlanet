#!/usr/bin/env python3
"""r18 visual：破戒恢复卡/换挡 sheet/深链自动开/journey 换挡行"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_shots")
os.makedirs(OUT, exist_ok=True)
USER = "cp_r18_vis_" + str(int(time.time()))
PWD = "CpR18#x2026"


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


async def seed_over(cid: int, uid: str, date: str, value: float) -> None:
    from app.db.database import async_session, init_db
    from app.services.goal_rule_service import daily_target
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.streak_service import day_number_of
    from app.repositories.challenge_repository import ChallengeRepository
    import datetime as dt

    await init_db()
    async with async_session() as session:
        ch = await ChallengeRepository().get_by_id(session, cid)
        day_number = day_number_of(str(ch.start_date), date)
        await CheckInRepository().create(session, {
            "challenge_id": cid, "user_id": uid, "day_number": day_number,
            "status": "completed", "timestamp": dt.datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(ch.unit),
            "target_value": float(daily_target(ch, day_number)),
            "goal_type": str(ch.goal_type), "direction": str(ch.direction),
            "completion_pct": 100.0,
        })
        await session.commit()


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    plan = [{"day": i + 1, "title": f"第{i+1}天", "description": "记录每一根", "tip": "",
             "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
            for i in range(30)]
    ch = api("POST", "/challenges/confirm", {
        "title": "r18 换挡视觉验收", "category": "quit", "duration_days": 30,
        "start_date": shift(2), "description": "E2E visual", "plan": plan,
        "source": "manual", "task_type": "counter", "target_value": 12.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    cid = int(ch["id"])
    asyncio.run(seed_over(cid, uid, shift(1), 15.0))

    from playwright.sync_api import sync_playwright
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

        page.goto(f"{BASE}/?ch={cid}&slip=1", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-ch-titlebar", timeout=30000)
        page.wait_for_selector(".cp-slip-card", timeout=15000)
        page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "r18_slip_card.png"))
        print("PASS 恢复卡渲染")

        page.wait_for_selector('[data-testid="ladder-shift-sheet"]', timeout=10000)
        page.wait_for_selector(".cp-shift-row", timeout=10000)
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(OUT, "r18_shift_sheet_deeplink.png"))
        print("PASS 深链自动开 sheet+预览")
        page.click('.cp-modal-close')
        page.wait_for_selector(".cp-modal-overlay", state="detached", timeout=8000)

        page.wait_for_timeout(500)
        btn = page.locator(".cp-slip-shift-btn")
        if btn.count() > 0:
            btn.click()
            page.wait_for_selector('[data-testid="ladder-shift-sheet"]', timeout=10000)
        else:
            print("INFO 恢复卡因深链会话已关，走 journey 再调入口")
            page.click(".cp-journey-adjust-btn")
            page.wait_for_selector('[data-testid="ladder-shift-sheet"]', timeout=10000)
        page.click('.cp-shift-chip[data-shift="3"]')
        page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(OUT, "r18_shift_preview3.png"))
        rows = page.locator(".cp-shift-row").all_inner_texts()
        print("预览行:", rows)
        page.click('.cp-modal-footer >> nth=0' if False else 'button.cp-btn-primary.cp-block')
        page.wait_for_selector(".cp-modal-overlay", state="detached", timeout=10000)
        page.wait_for_timeout(900)
        page.wait_for_selector(".cp-journey-adjust", timeout=15000)
        page.wait_for_timeout(400)
        page.screenshot(path=os.path.join(OUT, "r18_after_shift.png"))
        print("PASS 换挡落库+journey 换挡行")
        browser.close()

    real_errors = [e for e in errors if "favicon" not in e.lower()]
    print("JS errors:", real_errors[:4] if real_errors else "none")
    api("DELETE", f"/challenges/{cid}?mode=purge", token=token)
    print("cleanup done; shots:", OUT)


if __name__ == "__main__":
    main()
