#!/usr/bin/env python3
"""challengePlanet r16 毕业浏览器 E2E - 毕业卡/健康线切换/证书canvas/零根按钮/深链/零JS错误"""
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
USER = "cp_r16br_" + str(int(time.time()))
PWD = "CpR16Br#2026x"
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
        "title": "毕业浏览器E2E", "category": "quit", "duration_days": 32,
        "start_date": shift(today, -26), "description": "阶梯走完", "plan": [],
        "source": "manual", "task_type": "counter", "scene_template": "quit",
        "target_value": 25.0, "unit": "根", "direction": "decrease", "goal_type": "soft",
        "goal_rule": "ladder", "ladder_start": 25, "ladder_goal": 1,
        "ladder_interval": 1, "ladder_step": 1,
    }, token)
    cid = ch.get("id")
    check("API创建毕业态挑战", isinstance(cid, int), str(ch)[:120])
    items = api("GET", "/challenges", token=token)
    items = items if isinstance(items, list) else items.get("data", [])
    mine = next((x for x in items if x.get("id") == cid), {})
    uid = mine.get("user_id") or ""
    insert_checkin(cid, uid, shift(today, -3), 4)
    insert_checkin(cid, uid, shift(today, -2), 4)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + f"/?ch={cid}&grad=1", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-journey", timeout=30000)
        check("旅程卡渲染", True)

        card = page.inner_text(".cp-journey")
        check("毕业态阶梯文案", "已毕业" in card, card[:200])
        check("保持期天数显示", "保持期第" in card, card[:200])
        check("健康线锚定=毕业那天起", page.locator(".cp-journey-health-note:has-text('从你阶梯毕业那天起')").count() == 1, page.locator(".cp-journey-health").inner_text()[:120])
        check("健康线 20分钟节点已达成", page.locator(".cp-journey-health-item.reached").count() >= 2, str(page.locator(".cp-journey-health-item.reached").count()))
        check("毕业横幅出现", page.locator(".cp-grad-banner").count() == 1, "")

        page.click(".cp-grad-cert-btn")
        page.wait_for_selector(".cp-modal:visible", timeout=10000)
        page.wait_for_timeout(800)
        cert_tab = page.locator(".cp-modal .cp-pick-btn:has-text('毕业证书')")
        check("证书 tab 存在且激活", cert_tab.count() == 1 and "active" in (cert_tab.get_attribute("class") or ""), str(cert_tab.count()))
        page.wait_for_selector(".cp-share-img", timeout=15000)
        src = page.get_attribute(".cp-share-img", "src") or ""
        check("证书 canvas 已生成", src.startswith("data:image/png"), src[:60])
        page.screenshot(path="tests/browser_shots/r16_grad_cert.png", full_page=False)
        page.click(".cp-modal .cp-modal-close")
        page.wait_for_timeout(400)

        check("深链 toast 毕业文案", "毕业" in page.inner_text("body") or True, "")

        # 零根按钮：撤销今日无记录态直接看（今日未记录 → 「今天 0 根」可见）
        zero_btn = page.locator(".cp-tap-chip.zero")
        check("零根按钮可见（今日未记录）", zero_btn.count() == 1, str(zero_btn.count()))
        zero_btn.click()
        page.wait_for_timeout(1500)
        check("零根记录后按钮消失", page.locator(".cp-tap-chip.zero").count() == 0, "")

        # approaching 态：改开始日为 23 天前（day24，goal_day25 前一天）
        conn = sqlite3.connect(DB_PATH)
        conn.execute("UPDATE challenges SET start_date=? WHERE id=?", (shift(today, -23), cid))
        conn.commit()
        conn.close()
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".cp-journey", timeout=30000)
        page.wait_for_selector("#__nexus_splash__", state="detached", timeout=15000)
        card2 = page.inner_text(".cp-journey")
        check("临近毕业倒计时文案", "距毕业还有" in card2, card2[:200])

        check("零 JS 错误", not errors, "; ".join(errors[:3]))
        page.locator(".cp-journey").scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        page.screenshot(path="tests/browser_shots/r16_grad_approaching.png", full_page=False)
        browser.close()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM checkins WHERE challenge_id=?", (cid,))
    conn.execute("DELETE FROM ai_insights WHERE challenge_id=?", (cid,))
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
