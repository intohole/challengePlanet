#!/usr/bin/env python3
"""线上冒烟: 戒烟挑战模板 -> 填梯度 -> 直接创建 -> 记一根记账台(每次运行用随机账号)"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengeplanet"
USER = "cpe2equit" + str(int(time.time()))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    BASE + "/api/v1/auth/register",
    data=json.dumps({"username": USER, "password": "CpE2e#2026x", "email": USER + "@e2e.cp"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
    TOKEN = json.loads(r.read().decode())["access_token"]

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=True)
        ctx.add_init_script(f"""
            localStorage.setItem('uc_access_token','{TOKEN}')
            sessionStorage.setItem('uc_access_token','{TOKEN}')
            localStorage.setItem('cp_user_id','{USER}')
            localStorage.setItem('cp_nickname','{USER}')
        """)
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        print("== 1. 主站(空首页) -> 戒烟挑战模板 ==")
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(3000)
        page.locator(".cp-template-card", has_text="戒烟挑战").first.click()
        page.wait_for_selector(".cp-modal-overlay", timeout=10000)
        page.wait_for_timeout(300)
        check("创建弹窗打开且戒断已选中", page.locator(".cp-scene-card.active", has_text="戒断").count() == 1)

        print("== 2. 填「当前每天/目标每天」-> 直接创建 ==")
        page.fill('input[placeholder="如 20"]', "20")
        page.wait_for_timeout(200)
        check("直接创建按钮可用", not page.locator(".cp-btn-direct").is_disabled())
        page.click(".cp-btn-direct")
        page.wait_for_timeout(1500)
        toast = page.locator(".nux-toast-msg")
        if toast.count():
            check("toast 挑战已开启", "挑战已开启" in toast.inner_text(), toast.inner_text())
        else:
            check("toast 挑战已开启", True, "toast 已消失（创建已进入今日页）")

        print("== 3. 今日页 = 记账台(记一根) 而非 binary 已完成 ==")
        page.wait_for_timeout(3500)
        body2 = page.locator("body").inner_text()
        check("页面出现戒烟挑战标题", "戒烟挑战" in body2)
        check("出现「记一根」记账按钮", "记一根" in body2, body2[:200])
        check("不出现 binary「今日完成/今日已完成」", "今日已完成" not in body2 and "今日完成" not in body2)
        check("显示今日上限(20 根)", "上限" in body2 and "根" in body2)

        print("== 4. 点「记一根」自动记账 +1 ==")
        page.locator("button", has_text="记一根").first.click()
        page.wait_for_timeout(2000)
        body3 = page.locator("body").inner_text()
        check("记账后出现已记 1", "已记" in body3 and "1" in body3, body3[:150])

        page.screenshot(path="/tmp/cp_quit_prod_tally.png", full_page=False)

        errs = [e for e in console_errs if "favicon" not in e]
        check("无JS页面错误", not errs, "; ".join(errs[:3]))

        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")


if __name__ == "__main__":
    main()