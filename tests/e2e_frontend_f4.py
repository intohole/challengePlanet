#!/usr/bin/env python3
"""前4 浏览器 E2E：暗色清扫/galaxy 可读性/浮标礼让/静默守披露/词卡键盘（本地 8610 真库真链路）"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import random
import sys
import time
import urllib.request

BASE = os.environ.get("E2E_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
SPA = BASE + "/"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
OUT = os.path.join(REPO, "out", "fe4_shots")
os.makedirs(OUT, exist_ok=True)

STAMP = str(int(time.time()))
USER = "cp_fe4_e2e_" + STAMP
PWD = "CpFe4#x2026"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method, path, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    r.add_header("X-Forwarded-For", f"172.2{random.randint(10, 99)}.{random.randint(10, 99)}.{random.randint(10, 99)}")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def shift(days_ago):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def make_plan(days, task_type="counter", target=12.0, unit="根"):
    return [
        {"day": i + 1, "title": f"前4第{i+1}天", "description": "E2E", "tip": "",
         "task_type": task_type, "target_value": target, "unit": unit, "difficulty": 3, "steps": []}
        for i in range(days)
    ]


async def seed_day(challenge_id, user_id, date, value):
    from app.db.database import async_session, init_db
    from app.services.goal_rule_service import daily_target
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.streak_service import day_number_of
    from app.repositories.challenge_repository import ChallengeRepository
    await init_db()
    async with async_session() as session:
        ch = await ChallengeRepository().get_by_id(session, challenge_id)
        day_number = day_number_of(str(ch.start_date), date)
        await CheckInRepository().create(session, {
            "challenge_id": challenge_id, "user_id": user_id, "day_number": day_number,
            "status": "completed",
            "timestamp": datetime.datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(ch.unit),
            "target_value": float(daily_target(ch, day_number)),
            "goal_type": str(ch.goal_type), "direction": str(ch.direction),
            "completion_pct": 100.0,
        })
        await session.commit()


def create_challenge(token, title, extra, plan):
    ch = api("POST", "/challenges/confirm", dict({
        "title": title, "category": "quit", "duration_days": 40,
        "start_date": shift(3), "description": "E2E fe4", "plan": plan,
        "source": "manual", "task_type": "counter", "target_value": 12.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, **extra), token)
    d = ch.get("data") or ch
    return int(d["id"])


async def cleanup(challenge_ids):
    from app.db.database import async_session, init_db
    from sqlalchemy import delete
    from app.models.checkin import AIInsight, CheckIn
    from app.models.challenge import Challenge
    from app.models.recall import RecallEvent
    await init_db()
    async with async_session() as session:
        if challenge_ids:
            await session.execute(delete(CheckIn).where(CheckIn.challenge_id.in_(challenge_ids)))
            await session.execute(delete(AIInsight).where(AIInsight.challenge_id.in_(challenge_ids)))
            await session.execute(delete(RecallEvent).where(RecallEvent.challenge_id.in_(challenge_ids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(challenge_ids)))
        await session.commit()


def main():
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    assert token, str(st)[:200]

    cid = create_challenge(token, "前4静默守链", {}, make_plan(40))
    asyncio.run(seed_day(cid, uid, shift(3), 3.0))
    wch = create_challenge(token, "前4词卡键盘链", {
        "category": "learn", "task_type": "word", "target_value": 5.0, "unit": "词",
        "direction": "up", "goal_rule": "fixed", "goal_mode": "target",
        "ladder_start": 0, "ladder_goal": 0, "ladder_interval": 1, "ladder_step": 1,
    }, make_plan(40, "word", 5.0, "词"))

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        def new_ctx(theme="", viewport=None, reduce=False):
            vp = viewport or {"width": 1280, "height": 900}
            ctx = browser.new_context(viewport=vp, reduced_motion="reduce" if reduce else "no-preference")
            ctx.add_init_script(
                f"window.localStorage.setItem('uc_access_token','{token}');"
                + (f"window.localStorage.setItem('nx-theme','{theme}');" if theme else ""))
            return ctx

        # ---- A/B/C 静默守披露 + galaxy（亮色 1280）----
        ctx = new_ctx()
        page = ctx.new_page()
        errs: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.goto(SPA + f"?ch={cid}", wait_until="domcontentloaded")
        page.wait_for_selector(".cp-task-card", timeout=15000)
        page.wait_for_timeout(800)

        meta = page.evaluate("() => document.querySelector('meta[name=viewport]').getAttribute('content')")
        check("H1 viewport 含 interactive-widget", "interactive-widget=resizes-content" in meta, meta)

        page.evaluate("() => cpCompanion.open()")
        page.wait_for_selector(".nx-ai-chat", timeout=10000)
        page.evaluate("() => { window.appState.companionMeta = Object.assign({}, window.appState.companionMeta, { completed_days: 3, streak: 2, ladder_progress_pct: 33.33333333333333 }) }")
        page.wait_for_timeout(400)
        chip_txt = page.evaluate("() => { const c=[...document.querySelectorAll('.cp-companion-stat')].find(x=>x.textContent.includes('阶梯')); return c?c.textContent.trim():'' }")
        check("H2 阶梯百分比格式化", "阶梯 33.3%" in chip_txt and "33.333" not in chip_txt, chip_txt)
        page.evaluate("() => cpCompanion.close()")
        page.wait_for_timeout(300)

        page.evaluate("() => switchView('me')")
        page.wait_for_selector(".cp-ch-row", timeout=8000)
        body_txt = page.evaluate("() => document.body.innerText")
        check("A1 me 页静默守披露", "含 2 天静默守" in body_txt, body_txt[:200])
        tip = page.evaluate("() => { const m=document.querySelector('.cp-ch-row-meta[title]'); return m?m.getAttribute('title'):'' }")
        check("A2 静默守 title 解释", "不超上限就是守住" in tip, tip)
        bar = page.evaluate("""() => { const b=document.querySelector('.cp-ch-row .cp-progress-bar'); if(!b) return null; const s=getComputedStyle(b); const r=b.getBoundingClientRect(); return {display:s.display, h:Math.round(r.height), fill:Math.round(b.querySelector('.cp-progress-fill').getBoundingClientRect().width), barW:Math.round(r.width)} }""")
        check("A3 挑战行进度条可见", bool(bar) and bar["display"] == "block" and bar["h"] >= 4 and bar["barW"] > 20, str(bar))

        page.evaluate("() => switchView('home')")
        page.wait_for_timeout(400)
        page.evaluate("() => window.cpViews.home.switchTab('progress')")
        page.wait_for_selector("#galaxy-box svg", timeout=8000)
        page.wait_for_timeout(500)
        note = page.evaluate("() => { const n=document.querySelector('.cp-quick-stat-note'); return n?n.textContent:'' }")
        check("B1 报表连续注记", "含 2 天静默守" in note, note)
        num_style = page.evaluate("""() => { const t=document.querySelector('.galaxy-streak-num'); if(!t) return null; const s=getComputedStyle(t); return {paint:s.paintOrder, sw:s.strokeWidth, fill:s.fill} }""")
        check("C1 galaxy 主数字描边", bool(num_style) and num_style["paint"] == "stroke" and parseFloat_safe(num_style["sw"]) >= 3, str(num_style))
        dot_fill = page.evaluate("""() => { const d=document.querySelector('.galaxy-dot-future'); return d?getComputedStyle(d).fill:null }""")
        check("C2 轨道点亮色加深", dot_fill == "rgba(100, 116, 139, 0.3)", str(dot_fill))
        page.screenshot(path=os.path.join(OUT, "f4_progress_light.png"))

        # ---- D 暗色清扫 ----
        ctx.close()
        ctxd = new_ctx(theme="dark")
        paged = ctxd.new_page()
        paged.on("pageerror", lambda e: errs.append(str(e)))
        paged.goto(SPA + f"?ch={cid}", wait_until="domcontentloaded")
        paged.wait_for_selector(".cp-task-card", timeout=15000)
        paged.wait_for_timeout(600)
        paged.evaluate("() => cpCreate.open()")
        paged.wait_for_selector(".cp-scene-card", timeout=8000)
        scene_bg = paged.evaluate("() => getComputedStyle(document.querySelector('.cp-scene-card')).backgroundColor")
        check("D1 暗色场景卡非白", scene_bg != "rgb(255, 255, 255)", scene_bg)
        paged.evaluate("""() => { const c=window.appState.create; c.sceneTemplate='quit'; c.ladderStart=12; c.ladderGoal=3; }""")
        paged.wait_for_timeout(300)
        ladder_bg = paged.evaluate("() => getComputedStyle(document.querySelector('.cp-ladder-field input')).backgroundColor")
        check("D2 暗色阶梯输入非白", ladder_bg != "rgb(255, 255, 255)", ladder_bg)
        chip_bg = paged.evaluate("""() => { const el=[...document.querySelectorAll('.cp-form-row')].find(r=>r.textContent.includes('一句话')); return el?getComputedStyle(el.querySelector('.cp-sample-chip')).backgroundColor:null }""")
        check("D3 暗色示例chips非浅紫", chip_bg is not None and chip_bg != "rgb(245, 243, 255)", str(chip_bg))
        paged.screenshot(path=os.path.join(OUT, "f4_create_dark.png"))
        paged.evaluate("() => window.appState.create.show=false")
        paged.evaluate("() => { window.cpViews.home.switchTab('progress') }")
        paged.wait_for_selector("#galaxy-box svg", timeout=8000)
        label_fill = paged.evaluate("""() => { const t=document.querySelector('.galaxy-streak-label'); return t?getComputedStyle(t).fill:null }""")
        check("D4 galaxy标签暗色可读", bool(label_fill) and label_fill.startswith("rgba(255, 255, 255"), str(label_fill))
        paged.screenshot(path=os.path.join(OUT, "f4_progress_dark.png"))
        ctxd.close()

        # ---- E 浮标礼让（375）----
        ctx3 = new_ctx(viewport={"width": 375, "height": 812})
        p3 = ctx3.new_page()
        p3.on("pageerror", lambda e: errs.append(str(e)))
        p3.goto(SPA + f"?ch={cid}", wait_until="domcontentloaded")
        p3.wait_for_selector(".cp-task-card", timeout=15000)
        p3.wait_for_timeout(600)
        p3.evaluate("() => window.scrollTo(0, 400)")
        p3.wait_for_timeout(250)
        yield_state = p3.evaluate("""() => ({ cls: document.body.classList.contains('nx-dock-yield'), op: getComputedStyle(document.querySelector('.cp-fab')).opacity })""")
        check("E1 滚动让位类在场", yield_state["cls"] is True, str(yield_state))
        check("E2 FAB 让位透明", yield_state["op"] == "0.12", str(yield_state))
        p3.wait_for_timeout(1500)
        rest_state = p3.evaluate("""() => ({ cls: document.body.classList.contains('nx-dock-yield'), op: getComputedStyle(document.querySelector('.cp-fab')).opacity })""")
        check("E3 静止恢复", rest_state["cls"] is False and rest_state["op"] == "1", str(rest_state))
        ow = p3.evaluate("() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth })")
        check("E4 375 无页面级溢出", ow["sw"] <= ow["cw"] + 1, str(ow))
        ctx3.close()

        # ---- F reduced-motion 下礼让不安装 ----
        ctxr = new_ctx(reduce=True)
        pr = ctxr.new_page()
        pr.goto(SPA + f"?ch={cid}", wait_until="domcontentloaded")
        pr.wait_for_selector(".cp-task-card", timeout=15000)
        pr.evaluate("() => window.scrollTo(0, 400)")
        pr.wait_for_timeout(400)
        rcls = pr.evaluate("() => document.body.classList.contains('nx-dock-yield')")
        check("F1 reduced-motion 礼让禁用", rcls is False, str(rcls))
        ctxr.close()

        # ---- G 词卡键盘链（真 API 落库）----
        ctxw = new_ctx()
        pw = ctxw.new_page()
        pw.on("pageerror", lambda e: errs.append(str(e)))
        pw.goto(SPA + f"?ch={wch}", wait_until="domcontentloaded")
        pw.wait_for_selector(".cp-task-card", timeout=15000)
        pw.wait_for_timeout(600)
        pw.evaluate("() => window.cpViews.home.openWord()")
        pw.wait_for_selector(".cp-word-card", timeout=10000)
        for i in range(5):
            pw.wait_for_selector(".cp-word-card", timeout=8000)
            pw.keyboard.press("Space")
            pw.wait_for_selector(".cp-word-meaning", timeout=5000)
            if i == 0:
                check("G1 空格翻面", True)
            if i < 4:
                pw.keyboard.press("2")
            else:
                pw.keyboard.press("1")
            pw.wait_for_timeout(350)
        pw.wait_for_selector(".cp-word-done", timeout=10000)
        t = api("GET", f"/challenges/{wch}/today", token=token)
        td = t.get("data") or t
        check("G2 词卡键盘全链落库", bool(td.get("checked_in")) and float(td.get("today_total") or 0) == 5.0,
              f"checked_in={td.get('checked_in')} total={td.get('today_total')}")
        ctxw.close()

        check("J1 全程零 pageerror", len(errs) == 0, "; ".join(errs[:3]))
        browser.close()

    asyncio.run(cleanup([cid, wch]))
    print("cleanup done")

    print(f"\n== fe4 {len(passed)} passed / {len(failed)} failed ==")
    if failed:
        for n, dt in failed:
            print(f"  FAIL {n} :: {dt}")
        sys.exit(1)


def parseFloat_safe(v):
    try:
        return float(str(v).replace("px", ""))
    except Exception:
        return 0.0


if __name__ == "__main__":
    main()
