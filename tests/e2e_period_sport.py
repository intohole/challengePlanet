#!/usr/bin/env python3
"""端到端验证：运动/阅读计时场景——周维度双强目标、卡路里自动折算、计时器记录、用户只管记录。"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
USER, PWD = "cp_diag_probe", "Diag#2026probe"
OUT = os.path.join(os.path.dirname(__file__), "browser_shots", "v5")
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


CONFIRM_VARS = dict(scene_template="running", task_type="timer", target_value=30, unit="分钟",
                    direction="increase", goal_type="hard", decompose_mode="none", slot_hours=1,
                    slot_target_value=0, goal_rule="fixed", goal_mode="auto", ladder_start=0,
                    ladder_goal=0, ladder_interval=1, ladder_step=1, gender="男", age=28,
                    height_cm=170, weight_kg=70, goal_weight=60, activity_level=2)


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

        def mk(title: str, scene: str, tt: str, target: float, unit: str, period_target: float, period_unit: str, sport_met: float = 0.0):
            return page.evaluate("""(args) => {
                const days = 14, plan = [];
                for (let d = 1; d <= days; d++) plan.push({day: d, title: args.title, description: '周维度验收', task_type: args.tt,
                    target_value: args.target, unit: args.unit, difficulty: 1, steps: []});
                const body = {title: args.title, category: 'fitness', duration_days: days,
                    start_date: window.cpTodayStr(), description: '周维度验收', plan, source: 'web',
                    task_type: args.tt, scene_template: args.scene, target_value: args.target, unit: args.unit,
                    direction: 'increase', goal_type: 'hard', decompose_mode: 'none', slot_hours: 1,
                    slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto', ladder_start: 0,
                    ladder_goal: 0, ladder_interval: 1, ladder_step: 1, gender: '男', age: 28, height_cm: 170,
                    weight_kg: 70, goal_weight: 60, activity_level: 2,
                    period_days: 7, period_target: args.period_target, period_unit: args.period_unit,
                    sport_met: args.sport_met};
                return window.api.post('/challenges/confirm', body).then(r => (r.data || r).id);
            }""", {"title": title, "scene": scene, "tt": tt, "target": target, "unit": unit,
                   "period_target": period_target, "period_unit": period_unit, "sport_met": sport_met})

        run_cid = mk("周验收跑步" + str(int(__import__("time").time())), "running", "timer", 30, "分钟", 2000, "千卡", 9.8)
        check("创建运动(跑步/千卡周目标)成功", isinstance(run_cid, int), str(run_cid))
        print("  running cid:", run_cid)

        today0 = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {tt: t.task_type, target: t.today_target, period_unit: t.period_unit,
                period_target: t.period_target, period_total: t.period_total,
                week_settled: t.week_settled, calories_today: t.calories_today};
        }""", run_cid)
        print("  初始:", today0)
        check("运动今日=计时30分钟且周目标千卡口径", today0["tt"] == "timer" and today0["target"] == 30 and today0["period_unit"] == "千卡" and today0["period_target"] == 2000, str(today0))
        check("初始周未达标且卡路里为0", not today0["week_settled"] and today0["period_total"] == 0 and today0["calories_today"] == 0, str(today0))

        page.evaluate("() => window.cpLoadChallenges()")
        page.wait_for_timeout(1200)
        page.evaluate("window.cpSelectChallenge(%d)" % run_cid)
        page.evaluate("window.cpViews.home.switchTab('today')")
        for _ in range(15):
            ready = page.evaluate("""cid => {
                const h = window.cpViews.home;
                return h.loadedFor === cid && h.data && h.data.today && !h.data.loading;
            }""", run_cid)
            if ready:
                break
            page.wait_for_timeout(1200)
        page.wait_for_timeout(400)
        sw = page.evaluate("""() => ({
            stopwatch: !!document.querySelector('.cp-stopwatch'),
            swBtn: (document.querySelector('.cp-sw-btn.primary') || {}).innerText || '',
            weekCard: !!(document.body.innerText || '').includes('本周目标'),
        })""")
        check("计时场景显示开始/结束计时器", sw["stopwatch"] and "开始计时" in sw["swBtn"], str(sw))
        check("今日页显示本周目标卡片", sw["weekCard"], str(sw))

        page.click(".cp-sw-btn.primary")
        page.wait_for_timeout(3000)
        page.click(".cp-sw-btn.primary")
        page.wait_for_timeout(2000)
        after_sw = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {total: t.today_total, settled: t.settled, kcal: t.calories_today, checks: t.today_checkins.length,
                last_cal: t.today_checkins.length ? t.today_checkins[t.today_checkins.length-1].calories : 0};
        }""", run_cid)
        print("  计时器结束记录:", after_sw)
        check("计时结束自动入账分钟", after_sw["total"] > 0 and after_sw["checks"] >= 1, str(after_sw))
        check("卡路里自动折算(跑步MET9.8×70kg)", after_sw["kcal"] > 0 and after_sw["last_cal"] is not None and after_sw["last_cal"] > 0, str(after_sw))
        check("3分钟未达日目标(30)", not after_sw["settled"], str(after_sw))

        page.evaluate("""async cid => { await window.api.post('/challenges/' + cid + '/checkin', {value: 28}); }""", run_cid)
        page.wait_for_timeout(1800)
        done = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {total: t.today_total, settled: t.settled, kcal_today: t.calories_today,
                period_total: t.period_total, week_settled: t.week_settled, kcal_week: t.calories_week};
        }""", run_cid)
        print("  补齐30分钟:", done)
        check("补齐后系统判定今日达标", done["settled"], str(done))
        check("今日卡路里按MET自动合计≈343千卡", abs(done["kcal_today"] - 343.0) < 8, str(done))
        check("周目标按千卡口径未达标(≈343/2000)", not done["week_settled"] and abs(done["period_total"] - done["kcal_week"]) < 0.5, str(done))

        page.screenshot(path=os.path.join(OUT, "sport_weekcard.png"), full_page=False)
        cta_done = page.evaluate("""() => ({
            done: !!document.querySelector('.cp-cta-done'),
            kcalText: !!(document.body.innerText || '').includes('千卡'),
        })""")
        check("今日已完成+展示千卡", cta_done["done"] and cta_done["kcalText"], str(cta_done))

        rd_cid = mk("周验收阅读" + str(int(__import__("time").time())), "reading", "timer", 25, "分钟", 300, "分钟")
        check("创建阅读(分钟周目标)挑战成功", isinstance(rd_cid, int), str(rd_cid))
        today_r = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {unit: t.period_unit, pt: t.period_target, settled: t.week_settled};
        }""", rd_cid)
        check("阅读周目标为分钟口径(300)", today_r["unit"] == "分钟" and today_r["pt"] == 300 and not today_r["settled"], str(today_r))
        page.evaluate("""async cid => {
            await window.api.post('/challenges/' + cid + '/checkin', {value: 300});
        }""", rd_cid)
        page.wait_for_timeout(1500)
        week_done = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {settled: t.week_settled, pt: t.period_total};
        }""", rd_cid)
        check("阅读周累计达标(300/300)", week_done["settled"] and week_done["pt"] >= 300, str(week_done))

        check("全程无JS错误", len(errs) == 0, str(errs[:3]))
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()