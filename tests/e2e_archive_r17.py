#!/usr/bin/env python3
"""r17 旅程档案+第二程 浏览器 E2E：结束旅程双通道/档案区块/跨旅程统计/毕业卡最后一程"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "challenge.db")
USER = "cp_r17_e2e_" + str(int(time.time()))
PWD = "CpR17#x2026"
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
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def make_plan(days: int, cap: float) -> list[dict]:
    return [
        {"day": i + 1, "title": f"戒烟第{i+1}天", "description": "记录每一根", "tip": "多喝水",
         "task_type": "counter", "target_value": max(0.0, cap - i), "unit": "根",
         "difficulty": 3, "steps": []}
        for i in range(days)
    ]


def create_challenge(token: str, title: str, days: int = 14, start: str | None = None) -> int:
    ch = api("POST", "/challenges/confirm", {
        "title": title, "category": "quit", "duration_days": days,
        "start_date": start or time.strftime("%Y-%m-%d"), "description": "E2E 旅程档案",
        "plan": make_plan(days, 5.0), "source": "manual", "task_type": "counter",
        "target_value": 5.0, "unit": "根", "direction": "decrease", "goal_type": "soft",
    }, token)
    return int(ch["id"])


def shift(days_ago: int) -> str:
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st.get("data") or st).get("access_token")
    check("注册拿到token", bool(token), str(st)[:120])
    me_id = str(((st.get("data") or st).get("user") or {}).get("id") or "")

    cid1 = create_challenge(token, "E2E封存旅程挑战", start=shift(3))
    check("创建挑战1", cid1 > 0, str(cid1))
    conn = sqlite3.connect(DB)
    for i, v in enumerate([5.0, 3.0, 2.0]):
        conn.execute(
            "INSERT INTO checkins(challenge_id,user_id,day_number,status,timestamp,date,value,unit,"
            "target_value,goal_type,direction,completion_pct,mood,reflection,ai_feedback,context_tag)"
            " VALUES (?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?)",
            (cid1, me_id, i + 1, "completed", shift(3 - i), v, "根", 5.0,
             "soft", "decrease", 100.0, "", "", "", ""),
        )
    conn.commit()
    conn.close()
    check("直插3天历史打卡(打卡API恒记当日,防补记)", True)

    summaries = api("GET", "/archives/summary", token=token)
    check("summary端点可达", isinstance(summaries, dict), str(summaries)[:120])

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(BASE + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-ch-titlebar", timeout=30000)
        check("首页渲染出挑战标题栏", "E2E封存旅程挑战" in page.inner_text(".cp-ch-titlebar"))

        page.click(".cp-hero-share-btn[title='放弃挑战']")
        page.wait_for_selector(".cp-end-opt-main", timeout=10000)
        check("结束旅程弹窗出现", True)
        check("封存主按钮存在", page.locator(".cp-end-opt-main").count() == 1)
        check("彻底删除次按钮存在", page.locator(".cp-end-opt-purge").count() == 1)
        check("弹窗含挑战标题", "E2E封存旅程挑战" in page.inner_text(".cp-modal"))

        page.click(".cp-end-opt-main")
        page.wait_for_selector(".cp-end-opt-main", state="detached", timeout=10000)
        check("封存后弹窗关闭", True)
        page.wait_for_timeout(800)
        check("挑战从标题栏消失", page.locator(".cp-ch-titlebar").count() == 0,
              page.inner_text("body")[:150])

        page.click(".cp-nav-item:has-text('我的')")
        page.wait_for_selector(".cp-me-stats", timeout=15000)
        page.wait_for_selector(".cp-archive-row", timeout=15000)
        check("me页走过旅程区块出现", "走过的旅程" in page.inner_text("body"))
        row_txt = page.inner_text(".cp-archive-row")
        check("档案行含标题", "E2E封存旅程挑战" in row_txt, row_txt[:120])
        check("档案行含少抽", "少抽" in row_txt, row_txt[:120])
        stats_txt = page.inner_text(".cp-me-stats")
        check("统计卡出现累计少抽", "累计少抽" in stats_txt, stats_txt[:150])

        # 第二个挑战走彻底删除
        cid2 = create_challenge(token, "E2E彻底删除挑战")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".cp-ch-titlebar", timeout=30000)
        page.click(".cp-hero-share-btn[title='放弃挑战']")
        page.wait_for_selector(".cp-end-opt-purge", timeout=10000)
        page.click(".cp-end-opt-purge")
        page.wait_for_selector(".nux-confirm-overlay", timeout=10000)
        page.locator(".nux-confirm-overlay [data-role='confirm']").click()
        page.wait_for_selector(".cp-end-opt-purge", state="detached", timeout=10000)
        page.wait_for_timeout(800)
        check("彻底删除后挑战消失", page.locator(".cp-ch-titlebar").count() == 0)

        # 毕业卡 + 最后一程
        cid3 = create_challenge(token, "E2E毕业旅程挑战", days=30)
        conn = sqlite3.connect(DB)
        conn.execute("UPDATE challenges SET status='graduated', ladder_goal=3.0 WHERE id=?", (cid3,))
        conn.commit()
        conn.close()
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".cp-ch-titlebar", timeout=30000)
        page.wait_for_selector(".cp-grad-done", timeout=15000)
        grad_txt = page.inner_text(".cp-grad-done")
        check("毕业卡渲染最后一程文案", "最后一程" in grad_txt, grad_txt[:150])
        check("毕业卡有到0按钮", page.locator(".cp-grad-done button:has-text('到 0')").count() == 1)
        page.click(".cp-grad-done button")
        page.wait_for_selector(".cp-modal:has-text('创建挑战')", timeout=10000)
        raw = page.input_value(".cp-modal textarea, .cp-modal input[type='text']")
        check("创建面板预填最后一程文案", "彻底戒断" in raw or "戒断" in raw, raw[:120])

        real_errors = [e for e in errors if "favicon" not in e]
        check("无页面JS错误", not real_errors, str(real_errors[:2]))
        browser.close()

    arcs = api("GET", "/archives", token=token)
    check("archives端点1行档案", isinstance(arcs, list) and len(arcs) == 1, str(arcs)[:150])
    row = arcs[0] if isinstance(arcs, list) and arcs else {}
    check("档案avoided_total=5", row.get("avoided_total") == 5, str(row)[:150])
    check("档案completed_days=3", row.get("completed_days") == 3, str(row)[:120])
    summary = api("GET", "/archives/summary", token=token)
    check("summary聚合archive_count=1", summary.get("archive_count") == 1, str(summary))
    check("summary聚合active_count=1(毕业挑战仍在)", summary.get("active_count") == 1, str(summary))

    api("DELETE", f"/challenges/{cid3}?mode=purge", token=token)
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM journey_archives WHERE user_id=?", (me_id or USER,))
    conn.commit()
    conn.close()
    print(f"\n=== r17 旅程档案浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")


if __name__ == "__main__":
    main()
