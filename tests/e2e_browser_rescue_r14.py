#!/usr/bin/env python3
"""challengePlanet 断档救援浏览器 E2E - 救援卡/chips徽标排序/mood全场景/提醒设置/深链/零JS错误"""
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
USER = "cp_r14br_" + str(int(time.time()))
PWD = "CpR14Br#2026x"
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


def insert_checkin(cid: int, user_id: str, date: str, value: float = 1.0) -> None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, user_id, date + " 10:00:00", 1, date, "completed", "", "", "", "", 100.0, value, "次"),
    )
    conn.commit()
    conn.close()


def main() -> None:
    st_body = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st_body.get("data") or st_body).get("access_token")
    check("注册拿到token", bool(token), str(st_body)[:120])
    uid = str((st_body.get("data") or st_body).get("user", {}) or {}).strip() or ""
    today = time.strftime("%Y-%m-%d")

    plan = [
        {"day": i + 1, "title": f"阅读第{i+1}天", "description": "每天30页",
         "tip": "睡前读", "task_type": "counter", "target_value": 30.0,
         "unit": "页", "difficulty": 2, "steps": []}
        for i in range(21)
    ]
    ch = api("POST", "/challenges/confirm", {
        "title": "救援浏览器E2E阅读", "category": "learn", "duration_days": 21,
        "start_date": shift(today, -5), "description": "断档救援验证", "plan": plan,
        "source": "manual", "task_type": "counter", "target_value": 30.0,
        "unit": "页", "direction": "increase", "goal_type": "hard",
    }, token)
    cid = ch.get("id")
    check("API创建挑战", isinstance(cid, int), str(ch)[:120])
    user_id = api("GET", "/challenges", token=token)
    items = user_id if isinstance(user_id, list) else user_id.get("data", [])
    mine = next((x for x in items if x.get("id") == cid), {})
    uid = mine.get("user_id") or ""
    insert_checkin(cid, uid, shift(today, -4), 30)
    insert_checkin(cid, uid, shift(today, -3), 30)

    # 背词挑战（word 类型，验证 mood chips 全场景）
    ch2 = api("POST", "/challenges/confirm", {
        "title": "救援浏览器E2E背词", "category": "learn", "duration_days": 14,
        "start_date": today, "description": "mood chips 全场景", "plan": [
            {"day": i + 1, "title": f"背词第{i+1}天", "description": "20词",
             "tip": "", "task_type": "word", "target_value": 20.0,
             "unit": "词", "difficulty": 2, "steps": []} for i in range(14)
        ],
        "source": "manual", "task_type": "word", "target_value": 20.0,
        "unit": "词", "direction": "increase", "goal_type": "hard",
    }, token)
    cid2 = ch2.get("id")
    check("API创建背词挑战", isinstance(cid2, int), str(ch2)[:120])

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-task-card", timeout=30000)
        check("首页渲染", True)

        check("背词场景主CTA下有情境chips（全场景覆盖）", page.locator(".cp-checkin-box .cp-ctx-row:has-text('情境')").count() >= 1,
              f"count={page.locator('.cp-ctx-row').count()}")
        check("背词场景有心情chips", page.locator(".cp-checkin-box .cp-ctx-row:has-text('心情')").count() >= 1)

        # 深链直达救援挑战
        page.goto(BASE + f"/?ch={cid}&rescue=1", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-task-card", timeout=30000)
        check("深链切换到断档挑战", f"+{cid}" in page.content() or str(cid) in page.evaluate("() => window.appState.current && String(window.appState.current.id)"))

        page.wait_for_selector(".cp-rescue-card", timeout=15000)
        card_text = page.inner_text(".cp-rescue-card")
        check("救援卡渲染（跨挑战）", "断了 2 天" in card_text and "星轨还在" in card_text, card_text[:120])
        check("救援卡有补签按钮", page.locator(".cp-rescue-btn:has-text('补上')").count() >= 1, card_text[:120])

        # chips 徽标与排序：断档挑战应排第一
        first_chip = page.inner_text(".cp-ch-chip >> nth=0")
        check("断档挑战 chips 置顶带徽标", "⚡断2天" in first_chip, first_chip)

        # 点补签按钮 → mend 成功 → 卡消失
        page.click(".cp-rescue-btn:has-text('补上')")
        page.wait_for_function(
            "() => !document.querySelector('.cp-rescue-card') || !document.querySelector('.cp-rescue-card').innerText.includes('断了 2 天')",
            timeout=15000)
        check("补签后救援卡消失", True)

        # 「我的」页提醒设置
        page.click(".cp-nav-item:has-text('我的')")
        page.wait_for_selector(".cp-pref-row", timeout=15000)
        check("提醒设置卡渲染", True)
        hour_val = page.input_value(".cp-pref-hour")
        check("默认提醒 20 点", hour_val == "20", hour_val)
        page.select_option(".cp-pref-hour", "9")
        page.wait_for_timeout(800)
        prefs = api("GET", "/challenges/reminder/prefs", token=token)
        prefs_data = prefs.get("data", prefs)
        check("改小时落库 9 点", prefs_data.get("remind_hour") == 9, str(prefs_data))
        page.click(".cp-pref-toggle")
        page.wait_for_timeout(800)
        prefs = api("GET", "/challenges/reminder/prefs", token=token)
        prefs_data = prefs.get("data", prefs)
        check("开关关闭落库", prefs_data.get("enabled") is False, str(prefs_data))

        # squad tab 已移除
        check("底部导航无小队tab", page.locator(".cp-nav-item:has-text('小队')").count() == 0)

        check("零 JS 错误", not errors, "; ".join(errors[:3]))
        browser.close()

    print(f"\n=== 断档救援浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
    if failed:
        for name, detail in failed:
            print(f"  FAILED: {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
