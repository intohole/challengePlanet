#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CP_LOGIN_BASE", "https://songguokr.com/challengePlanet")
OUT = Path(__file__).parent / "browser_shots"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for name, vw in [("desktop", {"width": 1440, "height": 900}), ("mobile", {"width": 390, "height": 844})]:
        ctx = browser.new_context(viewport=vw, ignore_https_errors=True)
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
        page.wait_for_selector(".cp-login-input", timeout=30000)
        page.wait_for_timeout(1500)
        r = page.evaluate(
            "() => {"
            " const nb = document.querySelectorAll('.cp-nebula i').length;"
            " const stars = document.querySelectorAll('.cp-star').length;"
            " const dust = document.querySelectorAll('.cp-dust i').length;"
            " const orbit = !!document.querySelector('.cp-orbit-deco');"
            " const glow = !!document.querySelector('.cp-card-glow');"
            " const right = document.querySelector('.cp-login-right');"
            " const rightVisible = !!right && getComputedStyle(right).display !== 'none';"
            " const title = (document.querySelector('.cp-login-logo h1')||{}).textContent||'';"
            " return JSON.stringify({nb,stars,dust,orbit,glow,rightVisible,title});"
            "}"
        )
        print(f"[{name}]", r)
        obj = json.loads(r)
        check(f"{name}: 星云层4个光斑", obj["nb"] == 4, str(obj["nb"]))
        check(f"{name}: 星场已生成星星", obj["stars"] > 0, str(obj["stars"]))
        check(f"{name}: 登录卡片渲染", obj["title"] == "星轨挑战", str(obj["title"]))
        if name == "desktop":
            check(f"{name}: 星尘已生成", obj["dust"] > 0, str(obj["dust"]))
            check(f"{name}: 轨道星系可见", obj["orbit"] and obj["rightVisible"], str(obj))
            check(f"{name}: 卡片光晕存在", obj["glow"], "")
        else:
            check(f"{name}: 右侧场景已隐藏", not obj["rightVisible"], str(obj))
        page.screenshot(path=str(OUT / f"login_{name}.png"), full_page=True)
        check(f"{name}: 无JS错误", len(errs) == 0, str(errs[:3]))
        ctx.close()
    browser.close()

print(f"\n===== 登录页验证: {len(passed)} 通过, {len(failed)} 失败 =====")
for n, d in failed:
    print(f"FAILED: {n} :: {d}")
sys.exit(1 if failed else 0)
