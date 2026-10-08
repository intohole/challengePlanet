#!/usr/bin/env python3
"""r17 visual 截图：结束旅程弹窗 / me页档案+统计 / 毕业卡最后一程"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "challenge.db")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_shots")
os.makedirs(OUT, exist_ok=True)
USER = "cp_r17_vis_" + str(int(time.time()))
PWD = "CpR17#x2026"


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


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st.get("data") or st).get("access_token")
    me_id = str(((st.get("data") or st).get("user") or {}).get("id") or "")

    def make_challenge(title: str, days: int = 14, start: str | None = None) -> int:
        plan = [{"day": i + 1, "title": f"戒烟第{i+1}天", "description": "记录每一根", "tip": "多喝水",
                 "task_type": "counter", "target_value": 5.0, "unit": "根", "difficulty": 3, "steps": []}
                for i in range(days)]
        ch = api("POST", "/challenges/confirm", {
            "title": title, "category": "quit", "duration_days": days,
            "start_date": start or shift(0), "description": "旅程档案验收",
            "plan": plan, "source": "manual", "task_type": "counter",
            "target_value": 5.0, "unit": "根", "direction": "decrease", "goal_type": "soft",
        }, token)
        return int(ch["id"])

    cid1 = make_challenge("从12根减到3根", start=shift(3))
    conn = sqlite3.connect(DB)
    for i, v in enumerate([5.0, 3.0, 2.0]):
        conn.execute(
            "INSERT INTO checkins(challenge_id,user_id,day_number,status,timestamp,date,value,unit,"
            "target_value,goal_type,direction,completion_pct,mood,reflection,ai_feedback,context_tag)"
            " VALUES (?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?)",
            (cid1, me_id, i + 1, "completed", shift(3 - i), v, "根", 5.0,
             "soft", "decrease", 100.0, "", "", "", ""))
    conn.commit()
    conn.close()
    cid2 = make_challenge("考研单词打卡", days=30)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2)
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-ch-titlebar", timeout=30000)

        page.click(".cp-hero-share-btn[title='放弃挑战']")
        page.wait_for_selector(".cp-end-opt-main", timeout=10000)
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(OUT, "r17_end_modal.png"))
        page.click(".cp-modal-footer .cp-btn-ghost")
        page.wait_for_selector(".cp-end-opt-main", state="detached", timeout=8000)
        page.wait_for_selector(".cp-modal-overlay", state="detached", timeout=8000)

        api("DELETE", f"/challenges/{cid1}?mode=archive", token=token)
        page.wait_for_timeout(600)
        page.click(".cp-bottom-nav button:has-text('我的')")
        page.wait_for_selector(".cp-archive-row", timeout=15000)
        page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "r17_me_archives.png"))

        conn = sqlite3.connect(DB)
        conn.execute("UPDATE challenges SET status='graduated', ladder_goal=3.0 WHERE id=?", (cid2,))
        conn.commit()
        conn.close()
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".cp-grad-done", timeout=20000)
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(OUT, "r17_grad_nextleg.png"))
        browser.close()

    api("DELETE", f"/challenges/{cid2}?mode=purge", token=token)
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM journey_archives WHERE title IN ('从12根减到3根','考研单词打卡')")
    conn.execute("DELETE FROM checkins WHERE user_id=?", (me_id,))
    conn.commit()
    conn.close()
    print("shots saved:", OUT)


if __name__ == "__main__":
    main()
