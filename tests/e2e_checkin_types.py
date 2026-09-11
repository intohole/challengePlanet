#!/usr/bin/env python3
"""端到端验证：text 必填内容不空提交、step 按勾选清单由系统判定结算。"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
USER, PWD = "cp_diag_probe", "Diag#2026probe"
OUT = os.path.join(os.path.dirname(__file__), "browser_shots", "v4")
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
        try:
            page.wait_for_function("window.appState && window.appState.booted", timeout=180000)
        except Exception:
            pass
        page.wait_for_timeout(3000)

        text_cid = page.evaluate("""() => {
            const days = 14, title = '记录验收' + Date.now();
            const plan = [];
            for (let d = 1; d <= days; d++) plan.push({day: d, title, description: 'text空提交拦截验收', task_type: 'text',
                target_value: 1, unit: '篇', difficulty: 1, steps: []});
            return window.api.post('/challenges/confirm', {title, category: 'other', duration_days: days,
                start_date: window.cpTodayStr(), description: 'text空提交拦截验收', plan, source: 'web',
                task_type: 'text', scene_template: 'writing', target_value: 1, unit: '篇',
                direction: 'increase', goal_type: 'hard', decompose_mode: 'none', slot_hours: 1,
                slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto', ladder_start: 0,
                ladder_goal: 0, ladder_interval: 1, ladder_step: 1, gender: '', age: 26, height_cm: 170,
                weight_kg: 65, goal_weight: 60, activity_level: 2}).then(r => (r.data || r).id);
        }""")
        check("创建text挑战成功", isinstance(text_cid, int), str(text_cid))
        print("  text cid:", text_cid)

        empty_res = page.evaluate("""async cid => {
            try {
                await window.api.post('/challenges/' + cid + '/checkin', {value: 1, reflection: ''});
                return {blocked: false, detail: 'accepted'};
            } catch (e) { return {blocked: true, detail: String(e.message || e)}; }
        }""", text_cid)
        check("空reflection被后端拦截", empty_res["blocked"], str(empty_res))

        text_done = page.evaluate("""async cid => {
            const {data} = await window.api.post('/challenges/' + cid + '/checkin', {value: 1, reflection: '今天完成了500字写作练习'});
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {settled: t.settled, reflection: t.checkin_data && t.checkin_data.reflection};
        }""", text_cid)
        check("带内容提交后系统判定达标", text_done["settled"] and "500字" in (text_done["reflection"] or ""), str(text_done))

        step_cid = page.evaluate("""() => {
            const days = 14, title = '分步验收' + Date.now(), steps = ['预热', '主训练', '拉伸'];
            const plan = [];
            for (let d = 1; d <= days; d++) plan.push({day: d, title, description: 'step勾选判定验收', task_type: 'step',
                target_value: 3, unit: '项', difficulty: 1, steps});
            return window.api.post('/challenges/confirm', {title, category: 'fitness', duration_days: days,
                start_date: window.cpTodayStr(), description: 'step勾选判定验收', plan, source: 'web',
                task_type: 'step', scene_template: 'fitness', target_value: 3, unit: '项',
                direction: 'increase', goal_type: 'hard', decompose_mode: 'none', slot_hours: 1,
                slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto', ladder_start: 0,
                ladder_goal: 0, ladder_interval: 1, ladder_step: 1, gender: '', age: 26, height_cm: 170,
                weight_kg: 65, goal_weight: 60, activity_level: 2}).then(r => (r.data || r).id);
        }""")
        check("创建step挑战成功", isinstance(step_cid, int), str(step_cid))
        print("  step cid:", step_cid)

        page.evaluate("() => window.cpLoadChallenges()")
        page.wait_for_timeout(1500)
        page.evaluate("window.cpSelectChallenge(%d)" % step_cid)
        page.evaluate("window.cpViews.home.switchTab('today')")
        for _ in range(15):
            ready = page.evaluate("""cid => {
                const h = window.cpViews.home;
                return h.loadedFor === cid && h.data && h.data.today && !h.data.loading;
            }""", step_cid)
            if ready:
                break
            page.wait_for_timeout(1200)

        cta = page.evaluate("() => (document.querySelector('.cp-cta-main') || {}).innerText || ''")
        check("step主按钮=打开分步清单", "分步" in cta, cta)

        page.evaluate("window.cpViews.home.openStep()")
        page.wait_for_selector(".cp-step-item", timeout=15000)
        items = page.query_selector_all(".cp-step-item")
        check("分步清单显示3项", len(items) == 3, str(len(items)))
        page.evaluate("() => { document.querySelectorAll('.cp-step-item')[0].click(); }")
        page.wait_for_selector(".cp-step-item", timeout=10000)
        page.evaluate("() => { document.querySelectorAll('.cp-step-item')[1].click(); }")
        page.wait_for_timeout(300)
        btn = page.query_selector("button.cp-btn-checkin")
        check("勾选2项后可提交", btn and "2/3" in (btn.inner_text() or ""), (btn.inner_text() or "") if btn else "no btn")
        btn.click()
        page.wait_for_timeout(2500)
        half = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {settled: t.settled, total: t.today_total, checked_in: t.checked_in};
        }""", step_cid)
        print("  勾选2项后:", half)
        check("勾选2/3未达标可继续追加", not half["settled"] and half["total"] == 2, str(half))

        page.evaluate("window.cpViews.home.openStep()")
        page.wait_for_selector(".cp-step-item", timeout=10000)
        page.evaluate("() => { const items = document.querySelectorAll('.cp-step-item'); items[items.length - 1].click(); }")
        page.wait_for_timeout(300)
        btn2 = page.query_selector("button.cp-btn-checkin")
        btn2.click()
        page.wait_for_timeout(2500)
        full = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {settled: t.settled, total: t.today_total};
        }""", step_cid)
        check("补齐后系统判定达标", full["settled"] and full["total"] == 3, str(full))

        check("全程无JS错误", len(errs) == 0, str(errs[:3]))
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()