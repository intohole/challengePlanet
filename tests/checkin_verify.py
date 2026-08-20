#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
LOGIN = f"{BASE}/login"
USER, PWD = "cp_e2e", "CpE2e#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
    page = ctx.new_page()
    checkin_post = []
    checkin_resp = []
    page.on("request", lambda r: checkin_post.append(r.post_data) if r.method == "POST" and "/checkin" in r.url else None)
    page.on("response", lambda r: checkin_resp.append((r.status, r.url)) if "/checkin" in r.url and r.request.method == "POST" else None)
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))

    page.goto(LOGIN, wait_until="networkidle", timeout=60000)
    page.wait_for_selector(".cp-login-input", timeout=30000)
    page.fill("input.cp-login-input[type=text]", USER)
    page.fill("input.cp-login-input[type=password]", PWD)
    page.click(".cp-login-btn")
    page.wait_for_selector("#view-root", timeout=60000)
    page.wait_for_timeout(3500)

    cid = page.evaluate("() => { const c = window.appState.challenges.find(x => (x.completed_days||0) === 0); return c && c.id }")
    check("找到未打卡挑战", cid is not None, f"cid={cid}")
    page.evaluate(f"window.cpSelectChallenge({cid})")
    page.wait_for_timeout(3500)

    btn = page.query_selector(".nux-checkin-primary")
    check("打卡按钮渲染", btn is not None, "")
    btn_text = btn.inner_text() if btn else ""
    check("按钮为点亮今日", "点亮" in btn_text, btn_text)

    btn.click()
    page.wait_for_timeout(5000)

    check("发起POST /checkin", len(checkin_post) > 0, f"posts={len(checkin_post)}")
    if checkin_post:
        check("打卡payload value=1", json.loads(checkin_post[0]).get("value") == 1, checkin_post[0])
    if checkin_resp:
        check("checkin接口200", checkin_resp[0][0] == 200, str(checkin_resp))
    after = page.evaluate("() => { const V = window.cpViews.home; const t = V.data.today; return JSON.stringify({checked_in: !!(t && t.checked_in), toast:(document.querySelector('.cp-toast')||{}).innerText||''}) }")
    print("  点击后:", after)
    check("打卡状态变为已打卡", '"checked_in":true' in after, after)
    check("页面无JS错误", len(errs) == 0, str(errs[:3]))

    browser.close()

print(f"\n===== 打卡验证: {len(passed)} 通过, {len(failed)} 失败 =====")
for n, d in failed:
    print(f"FAILED: {n} :: {d}")
sys.exit(1 if failed else 0)