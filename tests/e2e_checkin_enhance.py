#!/usr/bin/env python3
from __future__ import annotations

import sys
from playwright.sync_api import sync_playwright

HARNESS = """
<body>
<div id="app"></div>
<div id="btn"></div>
<script>
window.__posts = []
window.appState = { current: { id: 123 } }
window.cpViews = { home: { data: { checking:false, taskValue:5, taskSteps:[], textValue:'', today:{} } } }
window.cpEsc = v => (v == null ? '' : String(v))
window.cpTaskTypeLabel = tt => ({counter:'计数',timer:'计时',step:'分步',text:'记录',binary:'打卡'}[tt] || '打卡')
window.cpErrMsg = () => ''
window.cpToast = window.cpLoadChallenges = () => {}
window.cpCelebrate = () => {}
window.cpPollTodayAi = null
const V = window.cpViews.home
V.rerender = () => {}
V._finishCheckin = async () => {}
V.load = async () => {}
window.api = { post: async (url, payload) => { window.__posts.push({url, payload}); return {data:{points_earned:1}} } }
</script>
"""


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.set_content(HARNESS)
        page.add_script_tag(path="static/js/views/home-checkin.js")
        page.wait_for_load_state("load")

        def run(expr: str) -> object:
            return page.evaluate(expr)

        V = "window.cpViews.home"

        passed: list[str] = []
        failed: list[tuple[str, str]] = []

        def check(name: str, cond: bool, detail: str = "") -> None:
            if cond:
                passed.append(name)
                print("  PASS", name)
            else:
                failed.append((name, detail))
                print("  FAIL", name, "::", detail)

        print("== 1. binary 一按即点火 (one-tap) ==")
        run(f"(() => {{ const btn = document.createElement('button'); btn.id='ig'; btn.innerHTML='{ '点燃今日' }';"
            f" btn.onpointerdown = e => {V}.igniteDown(e); btn.onpointerup = () => {V}.igniteUp(true);"
            f" document.getElementById('btn').appendChild(btn); return true; }})()")
        page.wait_for_timeout(50)
        posts_before = run("window.__posts.length")
        run("(() => { const b = document.getElementById('ig'); b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,pointerId:1})); return true; })()")
        page.wait_for_timeout(60)
        run("(() => { const b = document.getElementById('ig'); b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:1})); return true; })()")
        page.wait_for_timeout(120)
        posts_after = run("window.__posts.length")
        check("一按触发一次 /checkin", int(posts_after) == int(posts_before) + 1, f"posts={posts_before}->{posts_after}")
        check("binary payload value=1", run("(window.__posts[window.__posts.length-1]||{}).payload||{}") == {"value": 1.0}, str(run("window.__posts")))

        print("== 2. 长按取消不入库 (<300ms释放不触发, 滑离取消) ==")
        run("window.__posts.length = 0")
        run("(() => { const b = document.getElementById('ig'); b.dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,cancelable:true,pointerId:1})); return true; })()")
        page.wait_for_timeout(60)
        run("(() => { const b = document.getElementById('ig'); b.dispatchEvent(new PointerEvent('pointerleave',{bubbles:true,pointerId:1})); return true; })()")
        page.wait_for_timeout(120)
        check("滑离取消不触发", run("window.__posts.length") == 0, f"posts={run('window.__posts.length')}")

        print("== 3. 计数/计时统一绿色打卡 CTA ==")
        counter = run(f"{V}._counterUI({{task_target:20,task_unit:'个'}}, '')")
        timer = run(f"{V}._timerUI({{task_target:30,task_unit:'分钟'}}, '')")
        check("counter 用 cp-btn-checkin", "cp-btn-checkin" in str(counter) and "cp-btn-primary" not in str(counter), counter)
        check("timer 用 cp-btn-checkin", "cp-btn-checkin" in timer and "cp-btn-primary" not in timer, timer)
        check("CTA 文案统一为打卡完成", "打卡完成" in counter and "打卡完成" in timer, counter)

        print("== 4. 分步: 0项禁用 + X/Y 进度 ==")
        step0 = run(f"{V}._stepUI({{task_steps:['a','b','c']}}, '')")
        check("step 0项禁用", "cp-btn-checkin\" disabled" in step0, step0)
        check("step 显示 0/3", "0/3" in step0, step0)
        run("(() => { window.cpViews.home.data.taskSteps.push('a'); window.cpViews.home.data.taskSteps.push('b'); return true; })()")
        step2 = run(f"{V}._stepUI({{task_steps:['a','b','c']}}, '')")
        check("step 勾选后启用", "cp-btn-checkin\" " in step2 and "<button class=\"cp-btn-checkin\" disabled" not in step2, step2)
        check("step 显示 2/3", "2/3" in step2, step2)

        print("== 5. 文本: 未达标灰绿态 + 达标高亮 ==")
        run("window.cpViews.home.data.textValue = '短文'")
        textBelow = run(f"{V}._textUI({{task_target:20,task_unit:'字'}}, '')")
        check("text 未达标走浅色态", "background:rgba(5,150,105,.16)" in textBelow, textBelow)
        check("text 未达标仍可打卡", "打卡完成" in textBelow, textBelow)
        run("window.cpViews.home.data.textValue = '这是一段足够长度的记录内容用于今天的目标打卡'")
        textOk = run(f"{V}._textUI({{task_target:20,task_unit:'字'}}, '')")
        check("text 达标用实心绿", "background:rgba(5,150,105,.16)" not in textOk, textOk)

        check("页面无 JS 错误", len(errs) == 0, str(errs[:5]))

        browser.close()

    print(f"\n===== 打卡针对性增强验证: {len(passed)} 通过, {len(failed)} 失败 =====")
    for n, d in failed:
        print("FAILED:", n, "::", d)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()