#!/usr/bin/env python3
"""端到端验证二轮评审修复：period_days滚动窗口、week_target移除、卡路里/千卡周目标链路。"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
USER, PWD = "cp_diag_probe", "Diag#2026probe"
OUT = os.path.join(os.path.dirname(__file__), "browser_shots", "v6")
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

        def mk(title: str, period_days: int, period_unit: str, period_target: float, sport_met: float = 0.0, unit: str = "分钟"):
            return page.evaluate("""(args) => {
                const days = 30, plan = [];
                for (let d = 1; d <= days; d++) plan.push({day: d, title: args.title, description: '二轮验证', task_type: 'timer',
                    target_value: 30, unit: args.unit, difficulty: 1, steps: []});
                const body = {title: args.title, category: 'fitness', duration_days: days,
                    start_date: window.cpTodayStr(), description: '二轮验证', plan, source: 'web',
                    task_type: 'timer', scene_template: 'running', target_value: 30, unit: args.unit,
                    direction: 'increase', goal_type: 'hard', decompose_mode: 'none', slot_hours: 1,
                    slot_target_value: 0, goal_rule: 'fixed', goal_mode: 'auto', ladder_start: 0,
                    ladder_goal: 0, ladder_interval: 1, ladder_step: 1, gender: '男', age: 28, height_cm: 170,
                    weight_kg: 70, goal_weight: 60, activity_level: 2,
                    period_days: args.period_days, period_target: args.period_target,
                    period_unit: args.period_unit, sport_met: args.sport_met};
                return window.api.post('/challenges/confirm', body).then(r => (r.data || r).id);
            }""", {"title": title, "period_days": period_days, "period_unit": period_unit,
                   "period_target": period_target, "sport_met": sport_met, "unit": unit})

        cid = mk("二轮验证跑步" + str(int(__import__("time").time())), 14, "千卡", 2000, 9.8)
        check("创建14天周期千卡周目标挑战成功", isinstance(cid, int), str(cid))
        print("  cid:", cid)

        t0 = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {pd: t.period_days, has_wt: 'week_target' in t, total: t.period_total, unit: t.period_unit};
        }""", cid)
        check("period_days=14且响应无week_target", t0["pd"] == 14 and not t0["has_wt"] and t0["unit"] == "千卡", str(t0))

        page.evaluate("""async cid => {
            await window.api.post('/challenges/' + cid + '/checkin', {value: 30});
        }""", cid)
        page.wait_for_timeout(1500)
        t1 = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {kcal: t.calories_week, total: t.period_total, settled: t.week_settled};
        }""", cid)
        print("  打卡30分钟:", t1)
        check("卡路里折算≈343(千卡口径period_total)", abs(t1["kcal"] - 343.0) < 8 and abs(t1["total"] - t1["kcal"]) < 0.5, str(t1))
        check("14天窗口未达2000千卡", not t1["settled"], str(t1))

        page.evaluate("""async cid => {
            for (let i = 0; i < 6; i++) await window.api.post('/challenges/' + cid + '/checkin', {value: 30});
        }""", cid)
        page.wait_for_timeout(1800)
        t2 = page.evaluate("""async cid => {
            const t = await window.api.get('/challenges/' + cid + '/today').then(r => r.data || r);
            return {kcal: t.calories_week, settled: t.week_settled};
        }""", cid)
        print("  累计7×30分钟:", t2)
        check("累计7笔后千卡≥2000周目标达成", t2["settled"] and t2["kcal"] >= 2000, str(t2))

        check("全程无JS错误", len(errs) == 0, str(errs[:3]))
        browser.close()

    print(f"\n===== 验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print(f"FAILED: {n} :: {d}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()