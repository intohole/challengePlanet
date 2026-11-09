#!/usr/bin/env python3
"""r26 SUNSET 诚实终局浏览器 E2E：resting 卡渲染+复活动线+me 页告一段落档（真起服真浏览器）。

前置：tests/fe5_regression_env.py 已就绪（8610+stub 9535）。种子直接写环境库。
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
DB = os.environ.get("CP_DB", "/tmp/cp_fe5_regression.db")
USER = "cp_r26_br_" + str(int(time.time()))
PWD = "CpR26#2026x"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method: str, path: str, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def seed_resting(uid: str, title: str = "英语挑战") -> int:
    """ORM 通道种子（模型 default 补齐 NOT NULL 列，schema 漂移免疫）。"""
    import asyncio

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import app.models  # noqa: F401
    from app.core.datetime_utils import now_china
    from app.models.challenge import Challenge
    from app.models.checkin import CheckIn

    async def _seed() -> int:
        eng = create_async_engine("sqlite+aiosqlite:///" + DB)
        SM = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
        async with SM() as s:
            ch = Challenge(user_id=uid, title=title, category="learn", duration_days=66,
                           start_date="2026-09-09", end_date="2026-11-13", status="active",
                           task_type="binary", target_value=1.0, unit="次")
            s.add(ch)
            await s.flush()
            s.add(CheckIn(challenge_id=ch.id, user_id=uid, day_number=1, status="kept",
                          timestamp=now_china(), date="2026-10-04", value=1.0, unit="次",
                          target_value=1.0, goal_type="hard", direction="increase"))
            await s.commit()
            cid = int(ch.id)
        await eng.dispose()
        return cid

    return asyncio.run(_seed())


def main() -> int:
    from playwright.sync_api import sync_playwright

    # 应用→stub 的注册委托链超时（SDK 路径漂移），本地自铸 HS256（同 UC__JWT_SECRET，本地验签直通）
    import jwt

    uid = "r26br" + str(int(time.time()))
    now = int(time.time())
    SECRET = "cp-fe5-regression-secret" * 2
    token = jwt.encode({"sub": uid, "exp": now + 7200}, SECRET, algorithm="HS256")
    check("自铸 HS256 token", bool(token))

    cid = seed_resting(uid, title="戒烟挑战")
    check("种子挑战A：戒烟挑战（长眠候选）", cid > 0)
    cid2 = seed_resting(uid, title="英语挑战")
    check("种子挑战B：英语挑战（长眠候选）", cid2 > 0)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(BASE + "/", wait_until="domcontentloaded")
        page.evaluate(
            """([t, uid]) => { localStorage.setItem('uc_access_token', t);
                 localStorage.setItem('cp_user_id', uid);
                 localStorage.setItem('cp_nickname', 'R26实验'); }""",
            [token, uid],
        )
        page.goto(BASE + "/", wait_until="domcontentloaded")

        writes: list[str] = []
        page.on("request", lambda req: writes.append(req.method + " " + req.url) if req.method != "GET" else None)

        page.wait_for_selector('[data-testid="resting-card"]', timeout=10000)
        check("home 首屏 resting 卡（回流第一眼诚实）", True)
        lede = page.text_content(".cp-rest-lede") or ""
        check("诚实文案在场（不指责+战绩保留）", "告一段落" in lede and "坚持" in lede, lede[:60])
        check("无打卡主界面（resting 不显待打卡）", page.locator('[data-testid="revive-btn"]').count() == 1)

        page.click('[data-testid="revive-btn"]')
        # fe6: 复活加确认弹窗——点确定才真正 revive
        try:
            page.wait_for_selector(".nux-overlay", timeout=5000)
        except Exception:
            pass
        confirm_clicked = page.evaluate(
            "() => { const btns = Array.from(document.querySelectorAll('button'));"
            " const confirm = btns.find(b => b.textContent.trim() === '确定');"
            " if (confirm) { confirm.click(); return true } return false }"
        )
        check("确认弹窗出现并点确定", bool(confirm_clicked))
        try:
            page.wait_for_selector(".cp-rest-card", state="detached", timeout=15000)
            check("点击重新出发 → resting 卡退场", True)
        except Exception:
            diag = page.evaluate("""() => ({
                reviveFn: typeof (window.cpViews && cpViews.home && cpViews.home.revive),
                toast: (document.querySelector('[class*=toast]') || {}).textContent || '',
            })""")
            check("点击重新出发 → resting 卡退场", False, str(diag))
            raise

        page.wait_for_timeout(800)
        print("  [writes]", json.dumps(writes[:15], ensure_ascii=False))
        row = api("GET", "/challenges", token=token)
        items = row if isinstance(row, list) else (row.get("data") if isinstance(row.get("data"), list) else [])
        actives = [c for c in items if c.get("status") == "active"]
        check("后端确认恰好一个复活 active+计划重开",
              len(actives) == 1 and actives[0].get("start_date") == time.strftime("%Y-%m-%d"),
              json.dumps([(c.get("title"), c.get("status"), c.get("start_date")) for c in items], ensure_ascii=False))

        page.click(".cp-nav-item:has-text('我的')")
        page.wait_for_selector(".cp-ch-row", timeout=10000)
        page.wait_for_timeout(400)
        me_html = page.content()
        actives2 = [c for c in items if c.get("status") == "active"]
        revived_title = str(actives2[0].get("title")) if actives2 else ""
        rested_title = "戒烟挑战" if revived_title != "戒烟挑战" else "英语挑战"
        row_rest = page.locator(".cp-ch-row", has_text=rested_title)
        rest_txt = row_rest.first.inner_text() if row_rest.count() else ""
        check("me 页长眠挑战显示「告一段落」", "告一段落" in rest_txt, rest_txt[:120])
        check("me 页「重新出发」行动点在场", "fa-arrows-rotate" in (row_rest.first.inner_html() if row_rest.count() else ""), rest_txt[:120])
        row_active = page.locator(".cp-ch-row", has_text=revived_title)
        act_txt = row_active.first.inner_text() if row_active.count() else ""
        check("复活挑战在 me 页显示「进行中」（非谎报）", "进行中" in act_txt, act_txt[:120])
        check("me 页「告一段落」标签在场", "告一段落" in me_html)
        check("me 页「重新出发」行动点在场", "重新出发" in me_html)


        browser.close()

    print(f"\n{len(passed)} passed, {len(failed)} failed")
    for name, detail in failed:
        print(f"  FAIL-Detail {name}: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
