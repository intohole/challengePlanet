#!/usr/bin/env python3
from __future__ import annotations

import json
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
        check("登录成功进入首页", "login" not in page.url, page.url)

        cid = page.evaluate("""() => {
            const days = 30, title = '背词验收' + Date.now();
            const plan = [];
            for (let d = 1; d <= days; d++) plan.push({day: d, title, description: '背词自动打卡验收', task_type: 'word',
                target_value: 20, unit: '词', difficulty: 1, steps: []});
            const body = {title, category: 'learn', duration_days: days, start_date: window.cpTodayStr(),
                description: '背词自动打卡验收', plan, source: 'web', task_type: 'word', scene_template: 'english',
                target_value: 20, unit: '词', direction: 'increase', goal_type: 'hard', decompose_mode: 'none',
                slot_hours: 1, slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto',
                ladder_start: 0, ladder_goal: 0, ladder_interval: 1, ladder_step: 1,
                gender: '', age: 26, height_cm: 170, weight_kg: 65, goal_weight: 60, activity_level: 2};
            return window.api.post('/challenges/confirm', body).then(r => (r.data || r).id);
        }""")
        check("创建背词挑战成功", isinstance(cid, int), str(cid))
        print("  cid:", cid)

        today_before = page.evaluate("""async (cid) => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {task_type: t.task_type, target: t.task_target, settled: t.settled, total: t.today_total};
        }""", cid)
        check("初始未达标且任务类型=word", today_before["task_type"] == "word" and not today_before["settled"] and today_before["total"] == 0, str(today_before))

        page.evaluate("() => window.cpLoadChallenges()")
        page.wait_for_timeout(1500)
        page.evaluate("window.cpSelectChallenge(%d)" % cid)
        page.evaluate("window.cpViews.home.switchTab('today')")
        for _ in range(15):
            ready = page.evaluate("""cid => {
                const h = window.cpViews.home;
                return h.loadedFor === cid && h.data && h.data.today && !h.data.loading;
            }""", cid)
            if ready:
                break
            page.wait_for_timeout(1200)
        page.wait_for_timeout(400)

        cta = page.evaluate("() => (document.querySelector('.cp-cta-main') || {}).innerText || ''")
        check("主按钮=今日背词(无手动完成)", "今日背词" in cta and "完成" not in cta.split(chr(10))[0], cta)

        page.evaluate("window.cpViews.home.openWord()")
        page.wait_for_selector(".cp-word-card", timeout=20000)
        words = page.evaluate("() => (window.cpViews.home.data.wordCards || []).map(c => c.w)")
        print("  今日词卡前12:", words[:12])
        check("词卡已打乱(非字母序)", len(words) >= 5 and words != sorted(words), str(words[:12]))
        check("词卡数量=当日目标20", len(words) == 20, str(len(words)))
        page.screenshot(path=os.path.join(OUT, "word_cards_shuffled.png"), full_page=False)

        for i in range(20):
            page.wait_for_selector(".cp-word-card", timeout=10000)
            page.click(".cp-word-card")
            page.wait_for_selector(".cp-word-fb.known", timeout=5000)
            page.click(".cp-word-fb.known")
        page.wait_for_selector(".cp-cta-done", timeout=20000)
        page.wait_for_timeout(1500)

        after = page.evaluate("""async (cid) => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {settled: t.settled, total: t.today_total, target: t.today_target, checked_in: t.checked_in};
        }""", cid)
        print("  刷完20词后:", after)
        check("刷完即系统自动结算达标", after["settled"] and after["total"] >= after["target"] and after["checked_in"], str(after))

        done_ui = page.evaluate("""() => ({
            done: !!document.querySelector('.cp-cta-done'),
            manualBtn: !!document.querySelector('.cp-btn-checkin'),
            autoText: !!(document.body.innerText || '').includes('自动完成'),
        })""")
        check("主按钮=今日已完成", done_ui["done"], str(done_ui))
        check("无手动完成按钮", not done_ui["manualBtn"], str(done_ui))
        check("面板提示自动完成", done_ui["autoText"], str(done_ui))
        page.screenshot(path=os.path.join(OUT, "word_auto_done.png"), full_page=False)

        check("全程无JS错误", len(errs) == 0, str(errs[:3]))
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()