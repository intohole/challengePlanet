#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
USER, PWD = "cp_diag_probe", "Diag#2026probe"
OUT = os.path.join(os.path.dirname(__file__), "browser_shots", "v2")
os.makedirs(OUT, exist_ok=True)

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
        page = ctx.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(f"{BASE}/login", wait_until="networkidle", timeout=60000)
        page.wait_for_selector("input.nux-input[type=text]", timeout=30000)
        page.fill("input.nux-input[type=text]", USER)
        page.fill("input.nux-input[type=password]", PWD)
        page.evaluate("() => { const l = document.querySelector('label.nux-terms'); if (l) l.click(); }")
        page.click("button.nux-login-submit")
        page.wait_for_selector("#view-root", timeout=60000)
        page.wait_for_timeout(3000)
        check("登录成功进入首页", "login" not in page.url, page.url)

        info = page.evaluate("""() => ({
            chs: (window.appState.challenges || []).map(c => ({id: c.id, title: c.title, type: c.task_type, scene: c.scene_template})),
            banner: !!document.querySelector('.cp-brand-banner'),
            greetStats: !!document.querySelector('.cp-greet-stats'),
        })""")
        check("品牌banner已移除", not info["banner"], "banner仍存在")
        check("问候统计已移除", not info["greetStats"], "greet-stats仍存在")
        print("  challenges:", json.dumps(info["chs"], ensure_ascii=False))

        nux = page.evaluate("() => !!document.querySelector('.nux-checkin')")
        check("首页无日历组件(NuxCheckin)", not nux, "nux仍在首页")

        types = {}
        for ch in info["chs"]:
            types.setdefault(ch["type"] + ((':' + ch["scene"]) if ch["scene"] in ("pomodoro", "quit") else ""), []).append(ch["id"])

        for key, ids in types.items():
            cid = ids[0]
            page.evaluate("window.cpSelectChallenge(%d)" % cid)
            try:
                page.wait_for_selector(".cp-cta-main, .cp-cta-done", timeout=9000)
            except Exception:
                pass
            page.wait_for_timeout(1200)
            ui = page.evaluate("""() => {
                const el = document.querySelector('.cp-cta-main, .cp-cta-done');
                const chips = Array.from(document.querySelectorAll('.cp-extra-chip')).map(c => c.innerText);
                const taskTitle = (document.querySelector('.cp-task-title')||{}).innerText || '';
                return {
                    cta: el ? el.innerText.replace(/\\s+/g, ' ').trim() : null,
                    ctaDone: !!document.querySelector('.cp-cta-done'),
                    chips,
                    taskTitle,
                };
            }""")
            print(f"  [{key}] cta={ui['cta']!r} chips={ui['chips']}")
            page.screenshot(path=os.path.join(OUT, f"checkin_{key.replace(':','_')}.png"), full_page=False)
            check(f"[{key}] 主按钮渲染", ui["cta"] is not None, f"cta={ui['cta']}")
            check(f"[{key}] 无JS错误", len(errs) == 0, str(errs[:2]))

        page.evaluate("window.cpSelectChallenge(%d)" % types.get("counter", types.get("binary", [info["chs"][0]["id"]]))[0])
        page.wait_for_timeout(3200)
        page.evaluate("window.cpViews.home.switchTab('progress')")
        page.wait_for_timeout(2500)
        nux2 = page.evaluate("() => !!document.querySelector('.nux-checkin')")
        cal = page.evaluate("() => !!document.querySelector('.nux-checkin-calendar')")
        shot = page.screenshot(path=os.path.join(OUT, "progress_with_calendar.png"), full_page=False)
        check("进度页含打卡日历", nux2 and cal, f"nux={nux2} cal={cal}")

        page.evaluate("window.cpSelectChallenge(%d)" % types.get("binary", [1])[0])
        page.wait_for_timeout(3200)
        if page.query_selector(".cp-cta-main"):
            page.click(".cp-cta-main")
            page.wait_for_timeout(4000)
            after = page.evaluate("() => ({done: !!document.querySelector('.cp-cta-done'), err: !!document.querySelector('.cp-toast')})")
            check("binary 主按钮点击打卡成功", after["done"], str(after))
        else:
            done = page.evaluate("() => !!document.querySelector('.cp-cta-done')")
            check("binary 已打卡状态展示", done, "cta-done缺失")
        page.screenshot(path=os.path.join(OUT, "binary_after.png"), full_page=False)

        for key in ("word", "text"):
            if key not in types:
                continue
            cid = types[key][0]
            page.evaluate("window.cpSelectChallenge(%d)" % cid)
            page.wait_for_timeout(3200)
            chip = page.query_selector(".cp-extra-chip")
            if chip:
                chip.click()
                page.wait_for_selector(".cp-extra-panel, .cp-word-card, .cp-poem-box, .cp-step-list, .cp-text-input", timeout=5000)
                page.wait_for_timeout(800)
                panel = page.evaluate("() => !!document.querySelector('.cp-extra-panel, .cp-word-card, .cp-poem-box')")
                check(f"[{key}] 折叠面板展开", panel, key)
                page.screenshot(path=os.path.join(OUT, f"panel_{key}.png"), full_page=False)
            page.evaluate("window.cpViews.home.togglePanel('')")
            page.wait_for_timeout(400)

        print("\n控制台错误(前5):", errs[:5])
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()