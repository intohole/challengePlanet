#!/usr/bin/env python3
"""challengePlanet r15 减量旅程浏览器 E2E - journey卡/实时更新/里程碑庆祝/诱因chips/导航收敛/报告区块/零JS错误"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "challenge.db"
USER = "cp_r15br_" + str(int(time.time()))
PWD = "CpR15Br#2026x"
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


def shift(day: str, n: int) -> str:
    d = datetime.strptime(day, "%Y-%m-%d") + timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def insert_checkin(cid: int, user_id: str, date: str, value: float, unit: str = "根", target: float = 25.0) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit, target_value, goal_type, direction) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, user_id, date + " 10:00:00", 1, date, "completed", "", "", "", "", 100.0, value, unit, target, "soft", "decrease"),
    )
    conn.commit()
    conn.close()


def main() -> None:
    st_body = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st_body.get("data") or st_body).get("access_token")
    check("注册拿到token", bool(token), str(st_body)[:120])
    today = time.strftime("%Y-%m-%d")

    ch = api("POST", "/challenges/confirm", {
        "title": "戒烟浏览器E2E", "category": "quit", "duration_days": 30,
        "start_date": shift(today, -18), "description": "从每天25根减下来", "plan": [],
        "source": "manual", "task_type": "counter", "scene_template": "quit",
        "target_value": 25.0, "unit": "根", "direction": "decrease", "goal_type": "soft",
        "goal_rule": "ladder", "ladder_start": 25, "ladder_goal": 1,
        "ladder_interval": 1, "ladder_step": 1,
    }, token)
    cid = ch.get("id")
    check("API创建戒烟挑战", isinstance(cid, int), str(ch)[:120])
    items = api("GET", "/challenges", token=token)
    items = items if isinstance(items, list) else items.get("data", [])
    mine = next((x for x in items if x.get("id") == cid), {})
    uid = mine.get("user_id") or ""
    insert_checkin(cid, uid, shift(today, -3), 3)
    insert_checkin(cid, uid, shift(today, -2), 11)
    insert_checkin(cid, uid, shift(today, -1), 4)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + f"/?ch={cid}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-journey", timeout=30000)
        check("减量旅程卡渲染", True)

        card = page.inner_text(".cp-journey")
        check("hero 少抽 57 根", "57" in card and "已少抽" in card, card[:160])
        check("减幅 -76%", "-76%" in card, card[:160])
        check("省下约 ¥51", "¥51" in card, card[:160])
        check("50根+过半里程碑", card.count("🏅") == 2, card[:200])
        check("阶梯 19/25 档", "19/25" in card, card[:160])
        check("身体恢复线折叠存在", page.locator(".cp-journey-health summary").count() == 1, card[:160])
        page.click(".cp-journey-health summary")
        page.wait_for_selector(".cp-journey-health-item", timeout=5000)
        check("健康时间线展开 6 节点", page.locator(".cp-journey-health-item").count() == 6, "")
        check("口径注脚渲染", "疾控" in page.inner_text(".cp-journey-src") or "癌症协会" in page.inner_text(".cp-journey-src"), "")

        check("诱因 chips（压力/酒后/饭后）", page.locator(".cp-ctx-row:has-text('诱因')").count() == 1
              and "酒后" in page.inner_text(".cp-ctx-row:has-text('诱因')"), page.inner_text(".cp-ctx-row:has-text('诱因')")[:120])

        # 记一根 → journey 实时更新 + 里程碑庆祝（57≥50 crossed: prev keys 无 → 首开只记录；再记一笔跨 100? no）
        page.click(".cp-cap-main")
        page.wait_for_timeout(1500)
        card2 = page.inner_text(".cp-journey")
        check("记录后 journey 更新为 81", "81" in card2 and "¥73" in card2, card2[:160])

        # 排行 tab 已下架
        nav_text = page.inner_text(".cp-bottom-nav")
        check("导航无排行", "排行" not in nav_text, nav_text)

        # 报告 journey 区块
        page.evaluate("cpOpenShare && 0")
        page.evaluate("window.cpViews.home.openReport ? window.cpViews.home.openReport() : (window.appState.reportView={show:true,tab:'overview',loading:true,overview:null,hourly:null,context:null,mood:null,trend:null,heatmap:null,completion:null}, window.cpViews.home._loadReportData())")
        page.wait_for_selector(".cp-journey-embedded", timeout=20000)
        rep = page.inner_text(".cp-journey-embedded")
        check("报告区块减量旅程", "已少抽" in rep and "恢复线" in rep, rep[:160])

        check("零 JS 错误", not errors, "; ".join(errors[:3]))
        page.screenshot(path="tests/browser_shots/r15_journey_card.png", full_page=False)

        browser.close()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM checkins WHERE challenge_id=?", (cid,))
    conn.execute("DELETE FROM points_ledger WHERE user_id=?", (str(uid),))
    conn.execute("DELETE FROM challenges WHERE id=?", (cid,))
    conn.commit()
    conn.close()

    print(f"\n== 浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ==")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
