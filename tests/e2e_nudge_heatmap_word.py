#!/usr/bin/env python3
"""线上e2e: 戒烟风险提醒钩子(等级递进+去重) -> 进度页热力图 -> 背单词复习闭环(新用户)"""
from __future__ import annotations

import json
import ssl
import time
import urllib.request

from playwright.sync_api import sync_playwright

BASE = "https://songguokr.com/challengeplanet"
USER = "cpe2enudge" + str(int(time.time()))

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    BASE + "/api/v1/auth/register",
    data=json.dumps({"username": USER, "password": "CpE2e#2026x", "email": USER + "@e2e.cp"}).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
    TOKEN = json.loads(r.read().decode())["access_token"]

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def join_steps(step_str: str, args: list[tuple[str, str]]) -> str:
    return str(json.dumps(args))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=True)
        ctx.add_init_script(f"""
            localStorage.setItem('uc_access_token','{TOKEN}')
            sessionStorage.setItem('uc_access_token','{TOKEN}')
            localStorage.setItem('cp_user_id','{USER}')
            localStorage.setItem('cp_nickname','{USER}')
        """)
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("pageerror", lambda e: console_errs.append(str(e)))
        page.set_default_timeout(30000)

        def toast_now() -> str:
            page.wait_for_timeout(300)
            t = page.locator(".nux-toast-msg")
            return t.inner_text() if t.count() else ""

        def wait_toast_gone():
            try:
                page.wait_for_selector(".nux-toast-item", state="detached", timeout=6000)
            except Exception:
                pass
            page.wait_for_timeout(400)

        print("== 1. 创建戒烟挑战(当前每天=3) ==")
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(3500)
        page.locator(".cp-template-card", has_text="戒烟挑战").first.click()
        page.wait_for_selector(".cp-modal-overlay", timeout=10000)
        page.fill('input[placeholder="如 20"]', "3")
        page.wait_for_timeout(200)
        page.click(".cp-btn-direct")
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        check("画面出现「记一根」记账台", "记一根" in body)

        print("== 2. 风险提醒钩子: 等级递进(逼近->无->超限) + 同等级去重 ==")
        page.locator("button", has_text="记一根").first.click()
        page.wait_for_timeout(2000)
        t1 = toast_now()
        check("第1根(剩2根)触发逼近提醒", "还剩2根" in t1, t1)
        wait_toast_gone()

        page.locator("button", has_text="记一根").first.click()
        page.wait_for_timeout(2000)
        page.wait_for_timeout(600)
        t2 = page.locator(".nux-toast-item")
        check("第2根仍逼近但同级不重复提醒", t2.count() == 0, toast_now())
        page.wait_for_timeout(1000)

        page.locator("button", has_text="记一根").first.click()
        page.wait_for_timeout(2000)
        page.wait_for_timeout(600)
        t3 = page.locator(".nux-toast-item")
        check("第3根达到上限不提醒", t3.count() == 0, toast_now())
        page.wait_for_timeout(1000)

        page.locator("button", has_text="记一根").first.click()
        page.wait_for_timeout(2300)
        t4 = toast_now()
        check("第4根超限触发升级提醒", ("量到顶了" in t4) or ("超过目标" in t4), t4)
        wait_toast_gone()

        print("== 3. 进度页热力图 ==")
        page.locator(".cp-tab", has_text="进度").first.click()
        page.wait_for_timeout(1200)
        heat = page.locator(".cp-heatmap-card")
        check("进度页出现热度卡片", heat.count() == 1)
        cells = page.locator(".cp-heatmap .cp-heat-cell[data-v]")
        check("热力图有打卡数据格(同小时聚一格)", cells.count() >= 1 and int(cells.first.get_attribute("data-v")) >= 4, str(cells.count()))
        insight = page.locator(".cp-heatmap-insight").inner_text()
        check("戒烟场景洞察为高危时段", "记录最密" in insight and "最容易想" in insight, insight)

        print("== 4. 背单词: 自定义->英语->直接创建 ==")
        page.locator(".cp-fab").first.click()
        page.wait_for_selector(".cp-modal-overlay", timeout=10000)
        page.locator(".cp-scene-card", has_text="英语").first.click()
        page.wait_for_timeout(300)
        page.locator(".cp-btn-direct").click()
        page.wait_for_timeout(3000)
        if page.locator("button", has_text="今日背词").count() == 0 and page.locator(".cp-ch-chip", has_text="英语挑战").count():
            page.locator(".cp-ch-chip", has_text="英语挑战").first.click()
            page.wait_for_timeout(1500)
        body = page.locator("body").inner_text()
        check("英语挑战页面出现今日背词", "今日背词" in body, body[:160])

        print("== 5. 背单词复习闭环 ==")
        page.locator("button", has_text="今日背词").first.click()
        page.wait_for_timeout(1500)
        card_cnt = page.locator(".cp-word-card").count()
        check("词卡面板打开", card_cnt >= 1)
        first_card = page.locator(".cp-word-card").first

        def grade_one(kind: str) -> None:
            page.locator(".cp-word-card", has_text="").first.click()
            page.wait_for_timeout(150)
            page.locator(".cp-word-fb." + kind).first.click()
            page.wait_for_timeout(200)

        grade_one("forgot")
        grade_one("forgot")
        grade_one("blur")
        grade_one("known")
        grade_one("known")
        page.wait_for_timeout(300)
        saved = page.evaluate("() => { const k = Object.keys(localStorage).find(x => x.startsWith('cp_word_sess_')); return k ? JSON.parse(localStorage.getItem(k)) : null }")
        check("中途进度已存会话(断点续接)", saved is not None and saved.get("idx", 0) >= 5, str(saved))

        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3500)
        body = page.locator("body").inner_text()
        check("刷新后仍在本页", "背词" in body or "英语" in body)
        if page.locator("button", has_text="今日背词").count():
            page.locator("button", has_text="今日背词").first.click()
            page.wait_for_timeout(1200)
            prog = page.locator(".cp-word-progress span").last.inner_text()
            resume_ok = "/" in prog and prog.split("/")[0].strip().isdigit() and prog.split("/")[1].strip().isdigit()
            check("刷新后断点续接(进度小于20)", resume_ok and int(prog.split("/")[0]) < 20 and int(prog.split("/")[0]) >= 5, prog)

        # 把剩余卡片刷完: 已知词都点认识
        for _ in range(30):
            if page.locator(".cp-word-card").count() == 0:
                break
            page.locator(".cp-word-card").first.click()
            page.wait_for_timeout(80)
            page.locator(".cp-word-fb.known").first.click()
            page.wait_for_timeout(80)
        page.wait_for_timeout(2500)
        body = page.locator("body").inner_text()
        check("刷完出现质量回显(新词已学完+记住)", "新词已学完" in body, body[:200])

        rev = page.evaluate("() => { const k = Object.keys(localStorage).find(x => x.startsWith('cp_word_review_')); return k ? localStorage.getItem(k) : null }")
        parsed = json.loads(rev) if rev else {}
        vals = next(iter(parsed.values()), []) if isinstance(parsed, dict) else []
        check("忘记/模糊词已写入复习池(>=3)", len(vals) >= 3, str(parsed))
        sess_left = page.evaluate("() => Object.keys(localStorage).some(x => x.startsWith('cp_word_sess_'))")
        check("完成后清除会话断点", not sess_left)

        errs = [e for e in console_errs if "favicon" not in e]
        check("无JS页面错误", not errs, "; ".join(errs[:3]))

        ids = page.evaluate("() => (window.appState && window.appState.challenges || []).map(c => c.id)")
        for cid in ids:
            try:
                req = urllib.request.Request(BASE + f"/api/v1/challenges/{cid}", method="DELETE",
                                             headers={"Authorization": "Bearer " + TOKEN})
                urllib.request.urlopen(req, timeout=20, context=ctx)
            except Exception:
                pass
        print("    已清理测试挑战:", ids)

        page.screenshot(path="/tmp/cp_nudge_heatmap_word.png", full_page=False)
        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")


if __name__ == "__main__":
    main()