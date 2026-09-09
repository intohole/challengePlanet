#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
USER, PWD = "cp_diag_probe", "Diag#2026probe"
OUT = os.path.join(os.path.dirname(__file__), "browser_shots", "v3")
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

        cid = page.evaluate("""() => {
            const scene = window.cpSceneMap['running'];
            const days = 30, title = '结算验收' + Date.now();
            const plan = [];
            for (let d = 1; d <= days; d++) plan.push({day: d, title, description: '结算流程验收', task_type: 'counter',
                target_value: 3, unit: '公里', difficulty: 1, steps: []});
            const body = {title, category: 'fitness', duration_days: days, start_date: window.cpTodayStr(),
                description: '结算流程验收', plan, source: 'web', task_type: 'counter', scene_template: 'running',
                target_value: 3, unit: '公里', direction: 'increase', goal_type: 'hard', decompose_mode: 'none',
                slot_hours: 1, slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto',
                ladder_start: 0, ladder_goal: 0, ladder_interval: 1, ladder_step: 1,
                gender: '', age: 28, height_cm: 170, weight_kg: 70, goal_weight: 60, activity_level: 2};
            return window.api.post('/challenges/confirm', body).then(r => (r.data || r).id);
        }""")
        check("创建结算测试挑战", isinstance(cid, int), str(cid))
        print("  cid:", cid)

        def api_today():
            return page.evaluate("""async (cid) => {
                const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
                return {checked_in: t.checked_in, settled: t.settled, total: t.today_total,
                    target: t.today_target, remaining: t.remaining};
            }""", cid)

        s0 = api_today()
        check("初始未达标", not s0["settled"] and s0["total"] == 0, str(s0))

        s_half = page.evaluate("""async (cid) => { await window.api.post('/challenges/' + cid + '/checkin', {value: 1}); const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r); return {settled: t.settled, total: t.today_total, remaining: t.remaining}; }""", cid)
        print("  记1公里:", s_half)
        check("记1公里未达标且还差2", not s_half["settled"] and s_half["total"] == 1 and s_half["remaining"] == 2, str(s_half))

        s_done = page.evaluate("""async (cid) => { await window.api.post('/challenges/' + cid + '/checkin', {value: 2}); const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r); return {settled: t.settled, total: t.today_total}; }""", cid)
        print("  补齐到3公里:", s_done)
        check("达标即今日已完成", s_done["settled"] and s_done["total"] == 3, str(s_done))

        page.evaluate("window.cpSelectChallenge(%d)" % cid)
        page.evaluate("window.cpViews.home.switchTab('today')")
        for _ in range(10):
            ready = page.evaluate("""cid => {
                const h = window.cpViews.home;
                return h.loadedFor === cid && h.data && h.data.today && !h.data.loading && (document.querySelector('.cp-cta-done, .cp-cta-main') !== null);
            }""", cid)
            if ready:
                break
            page.wait_for_timeout(2000)
        page.wait_for_timeout(500)

        main_done = page.evaluate("() => ({done: !!document.querySelector('.cp-cta-done'), main: !!document.querySelector('.cp-cta-main'), hint: (document.querySelector('.cp-remain-hint')||{}).innerText || ''})")
        print("  达标UI:", main_done)
        check("达标后按钮=今日已完成", main_done["done"] and not main_done["main"] and not main_done["hint"], str(main_done))
        page.screenshot(path=os.path.join(OUT, "settled_done.png"), full_page=False)

        page.evaluate("window.cpViews.home.switchTab('insight')")
        page.wait_for_timeout(2500)
        snap = page.evaluate("() => ({snap: !!document.querySelector('.cp-phase-snap'), guidance: !!document.querySelector('.cp-guidance-card')})")
        print("  洞察页:", snap)
        check("洞察页显示阶段快照", snap["snap"], str(snap))
        check("洞察页无冗余guidance大卡", not snap["guidance"], str(snap))
        page.screenshot(path=os.path.join(OUT, "insight_compact.png"), full_page=False)

        check("全程无JS错误", len(errs) == 0, str(errs[:3]))
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()