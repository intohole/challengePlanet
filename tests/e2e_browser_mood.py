#!/usr/bin/env python3
"""ChallengePlanet 心情闭环浏览器 E2E - 心情chips/补选心情徽标/反馈流式/报表心情分布"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
USER = "cp_brmood_" + str(int(time.time()))
PWD = "CpBrM#2026x"
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
        "title": "浏览器心情闭环E2E", "category": "quit", "duration_days": 14,
        "start_date": today, "description": "记一根带心情", "plan": plan,
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

        page.click(".cp-cap-main")
        page.wait_for_selector(".cp-timeline-item.latest", timeout=15000)
        check("记一根后时间线出现最新记录", True)
        page.wait_for_selector(".cp-ctx-patch:has-text('感觉如何')", timeout=8000)
        check("最新记录出现心情补选chips", True)

        page.click(".cp-ctx-patch:has-text('感觉如何') .cp-ctx-chip:has-text('吃力')")
        page.wait_for_selector(".cp-timeline-mood", timeout=8000)
        check("补选心情后徽标出现", "😔" in page.inner_text(".cp-timeline-mood"),
              page.inner_text(".cp-timeline-mood"))

        mood_rows = page.locator(".cp-ctx-row:has-text('心情') .cp-ctx-chip")
        check("记一根面板有心情选择行", mood_rows.count() >= 4, f"count={mood_rows.count()}")

        page.click(".cp-ctx-row:has-text('心情') .cp-ctx-chip:has-text('不错')")
        page.click(".cp-cap-main")
        page.wait_for_function(
            "() => document.querySelectorAll('.cp-timeline-item').length >= 2", timeout=15000)
        check("第二根记录入列", True)
        today_view = api("GET", f"/challenges/{cid}/today", token=token)
        rows = today_view.get("today_checkins") or []
        check("第二笔mood=good落库", len(rows) >= 2 and rows[-1].get("mood") == "good",
              str(rows[-1])[:160] if rows else "no rows")

        page.wait_for_selector(".cp-ai-card", timeout=90000)
        page.wait_for_function(
            "() => { const c = document.querySelector('.cp-ai-card');"
            " return c && c.innerText.includes('教练反馈') && !c.innerText.includes('生成中')"
            " && c.innerText.replace('AI 教练反馈','').replace('今日陪伴','').trim().length > 10; }",
            timeout=120000,
        )
        fb_txt = page.inner_text(".cp-ai-card")
        check("AI反馈卡渲染完成", len(fb_txt.strip()) > 10, fb_txt[:120])
        check("反馈卡无生成中残留", "生成中" not in fb_txt, fb_txt[:120])

        page.click(".cp-tab:has-text('进度')")
        page.wait_for_selector(".cp-report-expand", timeout=15000)
        page.click(".cp-report-expand")
        page.wait_for_selector(".cp-report-tab", timeout=15000)
        page.click(".cp-report-tab:has-text('时段分布')")
        page.wait_for_selector(".cp-ctx-block:has-text('心情'), .cp-ctx-empty", timeout=15000)
        mood_block = page.locator(".cp-ctx-block:has-text('心情')")
        if mood_block.count() > 0:
            check("报表心情分布块渲染", True)
            bar_txt = mood_block.first.inner_text()
            check("心情块含吃力条目", "吃力" in bar_txt or "不错" in bar_txt, bar_txt[:120])
        else:
            check("报表心情分布块渲染", False, "显示的是空态提示而非数据块")

        real_errors = [e for e in errors if "favicon" not in e]
        check("无页面JS错误", not real_errors, str(real_errors[:2]))
        browser.close()

    api("DELETE", f"/challenges/{cid}", token=token)
    print(f"\n=== 心情闭环浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
