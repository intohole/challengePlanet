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


def shot(page, name: str) -> None:
    page.screenshot(path=os.path.join(OUT, name), full_page=False)


def sample_phase(page) -> dict:
    try:
        return page.evaluate(
            "() => { const c = window.appState.create; return {"
            "phase: c.phase, step: c.step, genDay: c.genDay, genTotal: c.genTotal,"
            "adjustHint: c.adjustHint, adjusting: c.adjusting, planLen: (c.plan||[]).length,"
            "editDays: c.editDays, error: c.error, show: c.show }; }"
        )
    except Exception as e:
        return {"err": str(e)}


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900}, ignore_https_errors=True)
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        nl_create_bodies: list[dict] = []

        def on_req(req):
            if "nl-create" in req.url and req.method == "POST":
                try:
                    nl_create_bodies.append(json.loads(req.post_data or "{}"))
                except Exception:
                    pass

        page.on("request", on_req)

        print("== 1. 登录 ==")
        page.goto(LOGIN, wait_until="networkidle", timeout=60000)
        page.wait_for_selector(".cp-login-input", timeout=30000)
        page.fill("input.cp-login-input[type=text]", USER)
        page.fill("input.cp-login-input[type=password]", PWD)
        shot(page, "1_login_filled.png")
        page.click(".cp-login-btn")
        page.wait_for_selector("#view-root", timeout=60000)
        page.wait_for_timeout(2500)
        check("登录跳转主界面", "/challengePlanet" in page.url and "login" not in page.url, page.url)

        print("== 2. 高风险破戒陪伴气泡(数据挑战) ==")
        data_ch = page.evaluate(
            "() => { const c = window.appState.challenges.find(x => (x.completed_days||0) > 0); "
            "return c ? {id: c.id, type: typeof c.id, title: c.title, completed: c.completed_days, streak: c.streak} : null; }"
        )
        print("  数据挑战:", data_ch)
        if data_ch:
            page.evaluate(f"window.cpSelectChallenge({json.dumps(data_ch['id'])})")
        page.wait_for_timeout(3500)
        cur = page.evaluate("() => ({id: window.appState.current && window.appState.current.id, g: !!(window.cpViews.home.data && window.cpViews.home.data.guidance)})")
        print("  current:", cur)
        comp = page.query_selector(".cp-companion")
        comp_text = comp.inner_text() if comp else ""
        shot(page, "2_companion_bubble.png")
        check("陪伴气泡渲染", comp is not None, "未找到 .cp-companion")
        check("高风险话术", "危险" in comp_text or "留意" in comp_text, comp_text[:120])
        check("风险原因标签", page.query_selector(".cp-companion-reasons") is not None, "")
        check("微行动建议", page.query_selector(".cp-companion-action") is not None, "")

        print("== 3. 打开创建弹窗 ==")
        page.evaluate("document.querySelector('.cp-fab')?.click() || window.cpCreate.open()")
        page.wait_for_selector(".cp-modal-overlay", timeout=15000)
        textarea = page.query_selector(".cp-modal textarea.cp-field")
        check("输入框存在", textarea is not None, "")
        if textarea:
            textarea.fill("我想21天养成每天阅读30分钟的习惯")
        shot(page, "3_raw_filled.png")

        print("== 4. 生成计划-实时进度反馈 ==")
        page.click("button:has-text('AI生成计划')")
        page.wait_for_timeout(800)
        progress_snap = page.evaluate(
            "() => (document.querySelector('.cp-gen-panel')||document.querySelector('.cp-gen-status')||{}).innerText || ''"
        )
        shot(page, "4_generating.png")
        check("进入生成中界面", progress_snap != "", progress_snap[:120])
        page.wait_for_function(
            "() => window.appState.create.phase === 'preview' || window.appState.create.phase === 'idle'",
            timeout=180000,
        )
        ph = sample_phase(page)
        shot(page, "4b_preview.png")
        check("进入preview", ph.get("phase") == "preview", str(ph))
        check("计划非空", ph.get("planLen", 0) >= 7, f"planLen={ph.get('planLen')}")

        print("== 5. 里程碑节奏条 ==")
        miles = page.query_selector(".cp-miles")
        miles_text = miles.inner_text() if miles else ""
        shot(page, "5_milestones.png")
        check("里程碑节奏条渲染", miles is not None, "未找到 .cp-miles")
        check("含出发节点", "出发" in miles_text, miles_text)
        check("含回顾节点", "回顾" in miles_text, miles_text)
        check("含收官冲刺", "收官冲刺" in miles_text, miles_text)
        mil_tags = page.query_selector_all(".cp-plan-day .cp-milestone-tag")
        check("计划日里程碑标记", len(mil_tags) >= 2, f"milestone_tags={len(mil_tags)}")

        print("== 6. 对话微调(adjust_hint) ==")
        n_before = len(nl_create_bodies)
        adj = page.query_selector("input.cp-field[maxlength='60']")
        check("调整输入框存在", adj is not None, "")
        if adj:
            adj.fill("太难了，每天任务减半，改成15分钟")
        shot(page, "6_adjust_filled.png")
        page.click(".cp-adjust-btn")
        page.wait_for_function(
            "() => window.appState.create.phase === 'preview' && !window.appState.create.adjusting",
            timeout=180000,
        )
        plan_after = page.evaluate("() => (window.appState.create.plan||[]).length")
        shot(page, "6b_adjust_preview.png")
        sent_hint = False
        for b in nl_create_bodies[n_before:]:
            if b.get("adjust_hint"):
                sent_hint = True
        check("调整请求携带adjust_hint", sent_hint, str(nl_create_bodies[n_before:])[:200])
        check("调整后plan非空", plan_after >= 7, f"len={plan_after}")

        print("== 7. 确认开启挑战 ==")
        page.click("button:has-text('开启挑战')")
        try:
            page.wait_for_selector(".cp-toast", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        toast = page.query_selector(".cp-toast")
        toast_text = toast.inner_text() if toast else ""
        shot(page, "7_challenge_created.png")
        check("创建成功提示", "挑战已开启" in toast_text or "挑战" in toast_text, toast_text[:80])

        print("== 8. 时段分布报表-作息洞察(数据挑战) ==")
        if data_ch:
            page.evaluate(f"window.cpSelectChallenge({json.dumps(data_ch['id'])})")
        page.wait_for_timeout(3500)
        expand = page.query_selector(".cp-report-expand")
        if expand:
            expand.click()
        else:
            page.evaluate("window.cpViews.home.openReport()")
        page.wait_for_selector(".cp-report-tabs", timeout=15000)
        page.click(".cp-report-tab:has-text('时段分布')")
        page.wait_for_function(
            "() => { const r = window.appState.reportView; return r && r.tab === 'hourly' && r.hourly; }",
            timeout=30000,
        )
        page.wait_for_timeout(1500)
        diag = page.evaluate(
            "() => { const r = window.appState.reportView.hourly; const c = window.appState.current; "
            "return {cur: c && c.id, items: (r.items||[]).length, peak: r.peak_value, insight: String(r.insight||'').slice(0,80), "
            "content: (document.querySelector('.cp-report-content')||{}).innerText ? document.querySelector('.cp-report-content').innerText.slice(0,120) : ''}; }"
        )
        print("  hourly diag:", diag)
        shot(page, "8_hourly.png")
        rose = page.query_selector(".cp-report-content .cp-rose-chart")
        check("时段分布图表渲染", rose is not None, "")
        ins = page.query_selector(".cp-report-content .cp-chart-insight, .cp-report-content .cp-rhythm")
        insight_text = ins.inner_text() if ins else ""
        check("作息洞察文本渲染", insight_text != "", insight_text[:150])
        rhythm = page.query_selector(".cp-report-content .cp-rhythm")
        rhythm_text = rhythm.inner_text() if rhythm else ""
        check("作息节奏总结", "作息节奏" in rhythm_text or "低谷" in rhythm_text, rhythm_text[:150])

        browser.close()

    print("\n===== 汇总 =====")
    print(f"通过 {len(passed)} 项, 失败 {len(failed)} 项")
    for name, d in failed:
        print(f"  FAILED: {name} :: {d}")
    if console_errs:
        print("\n控制台错误(前10条):")
        for e in console_errs[:10]:
            print("  -", e[:150])
    else:
        print("\n无控制台错误")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
