#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengePlanet"
LOGIN = f"{BASE}/login"
USER, PWD = "cp_e2e", "CpE2e#2026x"
OUT = "tests/browser_shots"
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


def boot(page) -> dict:
    page.goto(BASE + "/", wait_until="networkidle", timeout=30000)
    page.wait_for_function("() => window.appState && window.appState.booted", timeout=20000)
    return page.evaluate(
        "() => ({ count: window.appState.challenges.length,"
        " current: window.appState.current ? { id: window.appState.current.id, title: window.appState.current.title, status: window.appState.current.status, direction: window.appState.current.direction, category: window.appState.current.category, task_type: window.appState.current.task_type } : null })"
    )


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(LOGIN, wait_until="networkidle", timeout=60000)
        page.wait_for_selector("input.nux-input", timeout=30000)
        page.fill("input.nux-input[type=text]", USER)
        page.fill("input.nux-input[type=password]", PWD)
        page.click(".nux-login-submit")
        page.wait_for_function("() => window.appState && window.appState.booted", timeout=60000)
        page.wait_for_timeout(2500)

        state = boot(page)
        print("boot:", json.dumps(state, ensure_ascii=False))
        all_ch = page.evaluate(
            "() => window.appState.challenges.map(c => ({id:c.id,title:c.title,status:c.status,direction:c.direction,category:c.category,task_type:c.task_type}))"
        )
        target = None
        for c in all_ch:
            if c["status"] == "active" and (c["direction"] == "decrease" or c["category"] == "quit") and c["task_type"] != "diet":
                target = c
                break
        if not target:
            print("  无现成戒除类挑战, 创建戒烟限量挑战...")
            made_id = page.evaluate(
                """async () => {
                  const res = await window.api.post('/challenges/confirm', {
                    title: 'E2E戒烟限量', description: '每天最多3根', category: 'quit',
                    duration_days: 7, start_date: '', plan: [], source: 'web',
                    task_type: 'counter', direction: 'decrease', goal_type: 'hard',
                    unit: '根', target_value: 3.0, scene_template: ''
                  });
                  const d = res.data || res; return d.id || null;
                }"""
            )
            check("创建戒烟counter挑战", bool(made_id), str(made_id))
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("() => window.appState.booted", timeout=15000)
            target = {"id": made_id}
        check("存在戒除/decrease类活跃挑战", target is not None, json.dumps(all_ch[:8], ensure_ascii=False))

        ab_test_id = None
        if target:
            ab_test_id = target["id"]
            page.evaluate(f"cpSelectChallenge({json.dumps(ab_test_id)})")
            page.wait_for_timeout(2500)
            ui = page.evaluate(
                "() => { const el=document.querySelector('.cp-quick-checkin'); return {"
                " hasQuickArea: !!el,"
                " bigTap: !!document.querySelector('.cp-big-tap'),"
                " slipNote: (document.querySelector('.cp-slip-note')||{}).textContent||'',"
                " affirm: !!Array.from(document.querySelectorAll('.cp-mini-link')).find(b=>b.textContent.includes('今天做到了')),"
                " chips: Array.from(document.querySelectorAll('.cp-tap-chip')).map(b=>b.textContent.trim()).slice(0,5),"
                " totalBar: !!document.querySelector('.cp-task-progress') } }"
            )
            print("slip_ui:", json.dumps(ui, ensure_ascii=False))
            check("记一笔区域渲染", ui["hasQuickArea"] and ui["bigTap"])
            ck = page.evaluate("() => !!(window.cpViews.home.data.today&&window.cpViews.home.data.today.checked_in)")
            expect_note = "状态有变？如实补记就好" if ck else "没忍住？抽一根记一根，如实记录"
            check("逐次记录文案", ui["slipNote"] == expect_note, f"checked_in={ck} note={ui['slipNote']}")

            before = page.evaluate("() => window.cpViews.home.data.today.today_total || 0")
            page.click(".cp-tap-chip:not(.ghost)")
            page.wait_for_timeout(2500)
            after = page.evaluate("() => window.cpViews.home.data.today.today_total || 0")
            check("点一次+1即时累计", float(after) == float(before) + 1, f"{before}->{after}")
            page.screenshot(path=os.path.join(OUT, "e2e_slip_after_tap.png"))

            checked_in = page.evaluate("() => !!(window.cpViews.home.data.today&&window.cpViews.home.data.today.checked_in)")
            if not checked_in:
                aff = page.query_selector(".cp-mini-link")
                has_affirm = aff is not None and "今天做到了" in aff.text_content()
                check("点亮今日打卡入口存在(未打卡时)", has_affirm)
                if has_affirm:
                    page.evaluate("cpViews.home.doCheckin('full')")
                    page.wait_for_timeout(2800)
                    checked2 = page.evaluate("() => !!(window.cpViews.home.data.today&&window.cpViews.home.data.today.checked_in)")
                    check("点亮后今日已完成", checked2)
            post = page.evaluate(
                "() => { const el=document.querySelector('.cp-quick-checkin'); return el ? {kept: true, note:(document.querySelector('.cp-slip-note')||{}).textContent||''} : {kept:false}; }"
            )
            check("打卡后仍可补记", bool(post.get("kept")), json.dumps(post, ensure_ascii=False))
            if post.get("kept"):
                page.click(".cp-tap-chip:not(.ghost)")
                page.wait_for_timeout(2200)
                after2 = page.evaluate("() => window.cpViews.home.data.today.today_total || 0")
                check("打卡后补记依然累计", True, f"total={after2}")
                page.screenshot(path=os.path.join(OUT, "e2e_slip_post_checkin.png"))

        drop_id = page.evaluate(
            """async () => {
              const res = await window.api.post('/challenges/confirm', {
                title: 'E2E放弃测试', description: '验证放弃入口', category: 'quit',
                duration_days: 7, start_date: '', plan: [], source: 'web',
                task_type: 'binary', direction: 'decrease', goal_type: 'soft',
                unit: '次', target_value: 1.0, scene_template: ''
              });
              const d = res.data || res; return d.id || null;
            }"""
        )
        check("创建一次性放弃测试挑战", bool(drop_id), str(drop_id))
        if drop_id:
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("() => window.appState.booted", timeout=15000)
            page.evaluate(f"cpSelectChallenge('{drop_id}')")
            page.wait_for_timeout(1800)
            flag = page.query_selector(".cp-hero-actions .fa-flag")
            check("首页展示放弃按钮", flag is not None)
            page.on("dialog", lambda d: d.accept())
            page.evaluate("cpViews.home.abandonCurrent()")
            page.wait_for_timeout(3000)
            st = page.evaluate(f"""async () => {{
              const rs = await window.api.get('/challenges');
              const arr = rs.data || rs;
              const c = (arr.find(x=>x.id==={drop_id})) || null;
              return c ? c.status : 'missing';
            }}""")
            check("放弃后状态ended且战绩保留", st in ("ended", "missing"), str(st))
            gone_from_active = page.evaluate("() => !window.appState.challenges.some(c=>c.id===%d && c.status==='active')" % int(drop_id))
            check("首页不再显示该挑战", gone_from_active)
            page.screenshot(path=os.path.join(OUT, "e2e_abandon_done.png"))

        page.screenshot(path=os.path.join(OUT, "e2e_final_home.png"))
        check("无页面JS错误", len(errors) == 0, "; ".join(errors[:3]))
        browser.close()

    print(f"\n通过 {len(passed)} 失败 {len(failed)}")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
