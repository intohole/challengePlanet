#!/usr/bin/env python3
"""闪屏会话自适应守底：首载品牌档 1100ms / 同会话二次起快档 280ms / UI 登录跳转快档（本地 8610）"""
from __future__ import annotations

import json
import os
import random
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
STAMP = str(int(time.time()))
USER = "cp_splash_e2e_" + STAMP
PWD = "CpSplash#2026"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method, path, body=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("X-Forwarded-For", f"172.3{random.randint(10, 99)}.{random.randint(10, 99)}.{random.randint(10, 99)}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def timed_nav(page, url, timeout=20000):
    t0 = time.time()
    page.goto(url, wait_until="commit", timeout=timeout)
    page.wait_for_selector("#__nexus_splash__", state="attached", timeout=5000)
    attached = time.time() - t0
    page.wait_for_selector("#__nexus_splash__", state="detached", timeout=timeout)
    return attached, time.time() - t0


def main():
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    assert d.get("access_token"), str(st)[:200]

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))

        attached1, total1 = timed_nav(page, BASE + "/login")
        min1 = page.evaluate("() => window.NexusSplash && window.NexusSplash.minShow")
        seen = page.evaluate("() => sessionStorage.getItem('__nexus_splash_seen__')")
        check("S1 首载品牌档 minShow=1100", min1 == 1100, f"minShow={min1}")
        check("S2 首载最短展示 ≥1.5s", total1 >= 1.5, f"total={total1:.2f}s")
        check("S3 首载写入会话标记", seen == "1", f"seen={seen}")
        check("S4 首载闪屏注入即在场", attached1 < 1.0, f"attached={attached1:.2f}s")

        attached2, total2 = timed_nav(page, BASE + "/login")
        min2 = page.evaluate("() => window.NexusSplash && window.NexusSplash.minShow")
        check("S5 二次导航仍覆盖首屏", attached2 < 1.0, f"attached={attached2:.2f}s")
        check("S6 二次导航快档 minShow=280", min2 == 280, f"minShow={min2}")
        check("S7 二次导航快档退场 <1.4s", total2 < 1.4, f"total={total2:.2f}s")

        page.goto(BASE + "/login", wait_until="domcontentloaded")
        page.wait_for_selector("#nux-login-username", timeout=10000)
        page.fill("#nux-login-username", USER)
        page.fill("#nux-login-password", PWD)
        page.check(".nux-terms input[type=checkbox]")
        t0 = time.time()
        page.click("button.nux-login-submit")
        page.wait_for_url(BASE + "/", timeout=15000)
        page.wait_for_selector("#__nexus_splash__", state="detached", timeout=15000)
        total3 = time.time() - t0
        min3 = page.evaluate("() => window.NexusSplash && window.NexusSplash.minShow")
        mounted = page.evaluate("() => document.getElementById('app') && document.getElementById('app').getAttribute('data-v-app') !== null")
        check("S8 登录跳转落主页", page.url.rstrip("/") == BASE and mounted, f"url={page.url} mounted={mounted}")
        check("S9 登录跳转快档 minShow=280", min3 == 280, f"minShow={min3}")
        check("S10 登录跳转闪屏快速让位 <1.4s", total3 < 1.4, f"total={total3:.2f}s")

        check("S11 全程零 pageerror", not errs, str(errs[:2]))
        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
