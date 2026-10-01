#!/usr/bin/env python3
"""ChallengePlanet 情境闭环浏览器 E2E - 记一根带情境/补选情境徽标/报表情境分布/乐观更新"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
USER = "cp_br_" + str(int(time.time()))
PWD = "CpBr#2026x"
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


def main() -> None:
    st_body = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st_body.get("data") or st_body).get("access_token")
    check("注册拿到token", bool(token), str(st_body)[:120])
    today = time.strftime("%Y-%m-%d")
    plan = [
        {"day": i + 1, "title": f"戒烟第{i+1}天", "description": "记录每一根",
         "tip": "先喝水", "task_type": "counter", "target_value": 5.0,
         "unit": "根", "difficulty": 3, "steps": []}
        for i in range(14)
    ]
    ch = api("POST", "/challenges/confirm", {
        "title": "浏览器情境闭环E2E", "category": "quit", "duration_days": 14,
        "start_date": today, "description": "记一根带情境", "plan": plan,
        "source": "manual", "task_type": "counter", "target_value": 5.0,
        "unit": "根", "direction": "decrease", "goal_type": "soft",
    }, token)
    cid = ch.get("id")
    check("API创建挑战", isinstance(cid, int), str(ch)[:120])

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-cap-main", timeout=30000)
        check("首页渲染出记一根CTA", True)

        total_before = page.inner_text(".cp-cap-main em")
        page.click(".cp-cap-main")
        page.wait_for_selector(".cp-timeline-item.latest", timeout=15000)
        check("记一根后时间线出现最新记录", True)
        page.wait_for_selector(".cp-ctx-patch", timeout=8000)
        check("最新记录出现情境补选chips", True)

        page.click(".cp-cap-main")
        page.wait_for_function(
            "() => document.querySelectorAll('.cp-timeline-item').length >= 2", timeout=15000)
        check("第二根记录入列(连点不丢)", True)

        page.click(".cp-ctx-patch .cp-ctx-chip:has-text('压力')")
        page.wait_for_selector(".cp-ctx-badge:has-text('压力')", timeout=8000)
        check("补选情境后徽标出现", True)

        chips = page.locator(".cp-ctx-row .cp-ctx-chip")
        check("记一笔面板有情境选择行", chips.count() >= 5, f"count={chips.count()}")

        page.click(".cp-tab:has-text('进度')")
        page.wait_for_selector(".cp-report-expand", timeout=15000)
        page.click(".cp-report-expand")
        page.wait_for_selector(".cp-report-tab", timeout=15000)
        page.click(".cp-report-tab:has-text('时段分布')")
        page.wait_for_selector(".cp-ctx-block, .cp-ctx-empty", timeout=15000)
        if page.locator(".cp-ctx-block").count() > 0:
            check("报表情境分布块渲染", True)
            bar_txt = page.inner_text(".cp-ctx-block")
            check("情境块含压力条目", "压力" in bar_txt, bar_txt[:120])
            check("情境块含洞察行", page.locator(".cp-ctx-block .cp-chart-insight").count() > 0, "")
        else:
            check("报表情境分布块渲染", False, "显示的是空态提示而非数据块")

        real_errors = [e for e in errors if "favicon" not in e]
        check("无页面JS错误", not real_errors, str(real_errors[:2]))
        browser.close()

    api("DELETE", f"/challenges/{cid}", token=token)
    print(f"\n=== 情境闭环浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
