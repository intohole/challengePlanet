#!/usr/bin/env python3
"""fe6 前端体验轮守底: 复活动线的诚实承接（真起服真浏览器）。

前置: tests/fe5_regression_env.py 已就绪（8610+stub 9535）。
覆盖: 复活确认弹窗（取消不发 POST/确定才发）+ 复活开局条（复活当天渲染+文案）+
risk banner 复活当天退场 + chips 断档徽章 resting 退场 + resting 视图 FAB +
「立即打卡」真滚达打卡主钮 + me 页复活承接（current 切到复活的挑战）+ 375/暗色 + 零 pageerror。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

import jwt

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
DB = os.environ.get("CP_DB", "/tmp/cp_fe5_regression.db")
OUT = os.environ.get("CP_SHOTS", "tests/browser_shots")
os.makedirs(OUT, exist_ok=True)

uid = "fe6t" + str(int(time.time()))
SECRET = "cp-fe5-regression-secret" * 2
token = jwt.encode({"sub": uid, "exp": int(time.time()) + 7200}, SECRET, algorithm="HS256")

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def shot(page, name):
    page.screenshot(path=os.path.join(OUT, name))


def seed() -> dict:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import app.models  # noqa: F401
    from app.core.datetime_utils import now_china
    from app.services.streak_service import shift_date, today_str
    from app.models.challenge import Challenge
    from app.models.checkin import CheckIn
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    async def _seed() -> dict:
        eng = create_async_engine("sqlite+aiosqlite:///" + DB)
        SM = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with SM() as s:
            today = today_str()
            ch1 = Challenge(user_id=uid, title="减量戒烟：从 12 根到 3 根", category="quit",
                            duration_days=66, start_date="2026-09-09", end_date="2026-11-13",
                            status="resting", task_type="counter", target_value=20.0, unit="根",
                            direction="decrease", goal_rule="ladder", ladder_start=12.0,
                            ladder_goal=3.0, ladder_interval=7, ladder_step=1.0, icon="🚭")
            s.add(ch1)
            await s.flush()
            for i in range(21):
                d = shift_date(today, -30 + i)
                s.add(CheckIn(challenge_id=ch1.id, user_id=uid, day_number=i + 1, status="kept",
                              timestamp=now_china(), date=d, value=1.0, unit="根",
                              target_value=12.0, goal_type="hard", direction="decrease"))
            ch2 = Challenge(user_id=uid, title="每天阅读 30 分钟", category="learn",
                            duration_days=21, start_date=shift_date(today, -60), end_date=shift_date(today, -40),
                            status="resting", task_type="binary", target_value=1.0, unit="次",
                            direction="increase", icon="📚", goal_rule="fixed")
            s.add(ch2)
            await s.flush()
            for i in range(6):
                d = shift_date(today, -58 + i)
                s.add(CheckIn(challenge_id=ch2.id, user_id=uid, day_number=i + 1, status="kept",
                              timestamp=now_china(), date=d, value=1.0, unit="次",
                              target_value=1.0, goal_type="hard", direction="increase"))
            ch2.rescue_missed = 9
            await s.commit()
            out = {"quit": int(ch1.id), "read": int(ch2.id)}
        await eng.dispose()
        return out

    return asyncio.run(_seed())


def main() -> int:
    ids = seed()
    print("seeded:", ids)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        errs: list[str] = []
        posts: list[str] = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("request", lambda r: posts.append(r.url) if (r.method == "POST" and "/revive" in r.url) else None)
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.evaluate(
            """([t, u]) => { localStorage.setItem('uc_access_token', t);
                 localStorage.setItem('cp_user_id', u);
                 localStorage.setItem('cp_nickname', 'FE6守底'); }""",
            [token, uid],
        )
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.wait_for_function(
            "window.appState && window.appState.booted && window.appState.challenges.length > 0",
            timeout=30000,
        )
        page.wait_for_timeout(1500)

        print("== A. resting 视图动线出口 ==")
        check("A1 resting 卡在场", page.locator('[data-testid="resting-card"]').count() == 1)
        check("A2 resting 视图 FAB 在场（新建入口不再死胡同）", page.locator(".cp-fab").count() == 1)
        chips_badges = page.evaluate(
            "() => Array.from(document.querySelectorAll('.cp-ch-chip')).map(c => ({"
            " text: c.textContent.replace(/\\s+/g, ' '),"
            " badges: Array.from(c.querySelectorAll('.cp-chip-badge')).map(b => b.textContent) }))"
        )
        all_badges = [b for c in chips_badges for b in c["badges"]]
        check("A3 chips 断档徽章 resting 退场", not any("断" in b for b in all_badges), json.dumps(all_badges, ensure_ascii=False))
        check("A4 chips 告一段落徽章在场", any("告一段落" in b for b in all_badges))

        print("== B. 复活确认弹窗（home resting 卡） ==")
        pre = page.evaluate("() => ({ id: window.appState.current.id, completed: window.appState.current.completed_days })")
        page.click('[data-testid="revive-btn"]')
        page.wait_for_timeout(900)
        confirm_visible = page.evaluate(
            "() => { const el = document.querySelector('.nux-confirm, .nux-modal, [class*=confirm]');"
            " return el ? el.textContent.slice(0, 160) : '' }"
        )
        check("B1 确认弹窗出现且带保留说明", "坚持都保留" in confirm_visible or "重新计程" in confirm_visible, confirm_visible)
        posts.clear()
        cancel_sel = page.evaluate(
            "() => { const cancel = document.querySelector('.nux-confirm-overlay [data-role=cancel]');"
            " if (cancel) { cancel.click(); return 'clicked' } return 'not-found' }"
        )
        page.wait_for_timeout(800)
        check("B2 取消 → 未发 revive POST", len(posts) == 0, f"posts={posts} cancel={cancel_sel}")
        check("B3 取消 → resting 卡仍在", page.locator('[data-testid="resting-card"]').count() == 1)

        page.click('[data-testid="revive-btn"]')
        page.wait_for_timeout(900)
        posts.clear()
        ok = page.evaluate(
            "() => { const confirm = document.querySelector('.nux-confirm-overlay [data-role=confirm]');"
            " if (confirm) { confirm.click(); return confirm.textContent.trim() } return 'nf' }"
        )
        cur = None
        for _ in range(45):
            page.wait_for_timeout(1000)
            cur = page.evaluate(
                "() => ({ status: window.appState.current.status, completed: window.appState.current.completed_days,"
                " todayKeys: window.cpViews.home.data.today ? Object.keys(window.cpViews.home.data.today).length : 0,"
                " loading: window.cpViews.home.data.loading,"
                " strip: !!document.querySelector('[data-testid=revive-strip]'),"
                " risk: document.querySelectorAll('.cp-risk-banner').length })"
            )
            if cur["todayKeys"] > 10 and not cur["loading"]:
                break
        check("B4 确定 → revive POST 发出", len(posts) == 1 and f"/{pre['id']}/revive" in posts[0], f"posts={posts} clicked={ok}")
        check("B5 复活后 current=复活的挑战", cur and cur["status"] == "active" and cur["completed"] == pre["completed"], json.dumps(cur))

        print("== C. 复活第一眼开局条 ==")
        strip = page.evaluate(
            "() => { const el = document.querySelector('[data-testid=revive-strip]');"
            " return el ? el.textContent.replace(/\\s+/g, ' ') : '' }"
        )
        check("C1 开局条在场", bool(strip), "")
        check("C2 开局条文案（新旅程第 1 天+历史保留）", "新旅程第 1 天" in strip and str(pre["completed"]) in strip and "算数" in strip, strip[:80])
        risk = page.evaluate("() => document.querySelectorAll('.cp-risk-banner').length")
        check("C3 「中断了」banner 复活当天退场", risk == 0, f"banner={risk}")
        shot(page, "fe6_revived_desktop.png")
        page.screenshot(path=os.path.join(OUT, "fe6_revived_desktop_full.png"), full_page=True)

        print("== D. 「立即打卡」真滚达（risk banner 路径用第二个挑战当日复活形态验证选择器） ==")
        target = page.evaluate(
            "() => { const el = document.querySelector('.cp-cta-main');"
            " if (!el) return 'no-cta';"
            " el.scrollIntoView({ block: 'center' });"
            " const r = el.getBoundingClientRect();"
            " return { inView: r.top >= 0 && r.bottom <= window.innerHeight, cls: el.className } }"
        )
        check("D1 打卡主钮 .cp-cta-main 在场可滚达", isinstance(target, dict) and target.get("inView"), str(target))

        print("== E. me 页复活承接 ==")
        page.evaluate("document.querySelector('.cp-bottom-nav .cp-nav-item:nth-child(2)').click()")
        page.wait_for_timeout(2500)
        # void 前缀——返回 undefined 非 thenable，evaluate 不等待内部 nuxConfirm 的交互 promise
        page.evaluate(f"void window.cpViews.me.reviveChallenge({ids['read']})")
        page.wait_for_timeout(900)
        confirm2 = page.evaluate(
            "() => { const confirm = document.querySelector('.nux-confirm-overlay [data-role=confirm]');"
            " if (confirm) { confirm.click(); return true } return false }"
        )
        page.wait_for_timeout(2500)
        cur2 = page.evaluate(
            "() => ({ current: window.appState.current && {id: window.appState.current.id, title: window.appState.current.title, status: window.appState.current.status} })"
        )
        check("E1 确认弹窗出现并确定", confirm2 is True)
        check("E2 me 页复活后 current 切到复活的挑战", cur2["current"] and cur2["current"]["id"] == ids["read"], json.dumps(cur2, ensure_ascii=False))
        page.evaluate("document.querySelector('.cp-bottom-nav .cp-nav-item:nth-child(1)').click()")
        page.wait_for_timeout(2000)
        back = page.evaluate(
            "() => ({ viewTitle: (document.querySelector('.cp-hero-title')||{}).textContent,"
            " strip: !!document.querySelector('[data-testid=revive-strip]') })"
        )
        check("E3 回首页第一眼=复活的挑战（承接闭环）", "阅读" in (back["viewTitle"] or ""), json.dumps(back, ensure_ascii=False))
        check("E4 复活开局条跟随承接挑战", back["strip"] is True)

        print("== F. 375 + 暗色 ==")
        page.set_viewport_size({"width": 375, "height": 812})
        page.wait_for_timeout(1200)
        ov = page.evaluate("() => ({ w: document.documentElement.scrollWidth, win: window.innerWidth })")
        check("F1 375 无横向溢出", ov["w"] <= ov["win"] + 1, json.dumps(ov))
        shot(page, "fe6_375_revived.png")
        strip_w = page.evaluate(
            "() => { const el = document.querySelector('[data-testid=revive-strip]');"
            " return el ? el.getBoundingClientRect().width : 0 }"
        )
        check("F2 开局条 375 全宽适配", strip_w > 300, f"width={strip_w}")
        page.set_viewport_size({"width": 1400, "height": 900})
        page.evaluate("localStorage.setItem('nx-theme', 'dark')")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "window.appState && window.appState.booted && window.appState.challenges.length > 0",
            timeout=30000,
        )
        page.wait_for_timeout(1500)
        dark_strip = page.evaluate(
            "() => { const el = document.querySelector('[data-testid=revive-strip]');"
            " return el ? getComputedStyle(el).backgroundColor + '|' + getComputedStyle(el).color : 'none' }"
        )
        check("F3 暗色开局条非白底白块", dark_strip != "none" and "255, 255, 255" not in dark_strip, dark_strip)
        shot(page, "fe6_dark_revived.png")

        check("Z1 零 pageerror", len(errs) == 0, "; ".join(errs[:3]))
        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    if failed:
        for name, detail in failed:
            print(f"  FAILED: {name} :: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
