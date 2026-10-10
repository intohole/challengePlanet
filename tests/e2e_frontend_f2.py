#!/usr/bin/env python3
"""前2 旅程有终章 浏览器 E2E：视图串台根治/毕业态即时渲染/旅程回看弹窗/档案微故事/浮点fmt/图标语义"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "challenge.db")
USER = "cp_fe2_e2e_" + str(int(time.time()))
PWD = "CpFe2#x2026"
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


def shift(days_ago: int) -> str:
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def create_quit(token: str, title: str, days: int, start: str, cap: float, start_val: float) -> int:
    plan = [
        {"day": i + 1, "title": f"第{i+1}天", "description": "", "task_type": "counter",
         "target_value": max(0.0, start_val - i * (start_val - cap) / max(1, days - 1)), "unit": "根", "difficulty": 3}
        for i in range(days)
    ]
    ch = api("POST", "/challenges/confirm", {
        "title": title, "category": "quit", "duration_days": days, "start_date": start,
        "description": "E2E 前2", "plan": plan, "source": "manual", "task_type": "counter",
        "target_value": start_val, "unit": "根", "direction": "decrease", "goal_type": "soft",
    }, token)
    cid = int(ch["id"])
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE challenges SET ladder_start=?, ladder_goal=?, ladder_interval=5 WHERE id=?", (start_val, cap, cid))
    conn.commit()
    conn.close()
    return cid


def insert_history(cid: int, uid: str, start_ago: int, count: int, base: float, step: float) -> None:
    conn = sqlite3.connect(DB)
    d = start_ago
    for i in range(1, count + 1):
        date = shift(d)
        conn.execute(
            "INSERT INTO checkins(challenge_id,user_id,day_number,status,timestamp,date,value,unit,"
            "target_value,goal_type,direction,completion_pct,mood,reflection,ai_feedback,context_tag)"
            " VALUES (?,?,?,?,datetime('now'),?,?,?,?,?,?,?,?,?,?,?)",
            (cid, uid, i, "completed", date, round(base - (i - 1) * step, 1), "根", base,
             "soft", "decrease", 100.0, "", "", "", ""),
        )
        d = max(0, d - 1)
    conn.commit()
    conn.close()


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    token = (st.get("data") or st).get("access_token")
    me_id = str(((st.get("data") or st).get("user") or {}).get("id") or "")
    check("注册拿到token", bool(token), str(st)[:120])

    cid_grad = create_quit(token, "E2E毕业旅程20根起步", 40, shift(34), 3.0, 20.0)
    insert_history(cid_grad, me_id, 34, 34, 20.0, 0.5)
    conn = sqlite3.connect(DB)
    conn.execute("UPDATE challenges SET status='graduated' WHERE id=?", (cid_grad,))
    conn.commit()
    conn.close()

    cid_act = create_quit(token, "E2E活跃冲刺", 66, shift(9), 0.0, 8.0)
    insert_history(cid_act, me_id, 9, 9, 8.0, 0.125)

    cid_arc = create_quit(token, "E2E封存的旧旅程", 21, shift(60), 5.0, 15.0)
    insert_history(cid_arc, me_id, 60, 11, 15.0, 1.0)
    api("DELETE", f"/challenges/{cid_arc}", token=token)
    arcs = api("GET", "/archives", token=token)
    check("档案端点1行", isinstance(arcs, list) and len(arcs) == 1, str(arcs)[:120])
    arc = arcs[0] if isinstance(arcs, list) and arcs else {}
    check("档案含baseline/final_cap", arc.get("baseline") == 15.0 and arc.get("final_cap") == 5.0, str(arc)[:200])

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
        page.wait_for_timeout(1200)

        # -- P0-A 视图串台：AI反馈流在途时切 me，DOM 不被 home 覆盖 --
        h1_before = page.evaluate("(document.querySelector('.cp-greet h1')||{}).textContent")
        page.click(".cp-nav-item:has-text('我的')")
        page.wait_for_timeout(3000)
        h1_after = page.evaluate("(document.querySelector('.cp-greet h1')||{}).textContent")
        view_state = page.evaluate("window.appState.view")
        check("切me后h1仍是我的(视图串台根治)", h1_after == "我的" and view_state == "me",
              f"before={h1_before} after={h1_after} view={view_state}")
        check("me页统计卡渲染", page.locator(".cp-me-stats").count() == 1)

        # -- 档案行 button 化 + 微故事 --
        row = page.locator(".cp-archive-row")
        check("档案行可聚焦button", row.count() == 1 and row.first.evaluate("el => el.tagName") == "BUTTON",
              str(row.count()))
        row_txt = row.first.inner_text()
        check("档案行微故事含阶梯起点终点", "15→5" in row_txt, row_txt[:120])
        check("档案行微故事含少抽", "少抽 55" in row_txt, row_txt[:120])
        check("档案行键盘可达", row.first.evaluate("el => el.tabIndex >= 0"), "")

        # -- P0-C 旅程回看弹窗 --
        row.first.click()
        page.wait_for_selector(".cp-modal", timeout=8000)
        modal_txt = page.inner_text(".cp-modal")
        check("回看弹窗标题", "旅程回看" in modal_txt, modal_txt[:100])
        check("弹窗含日期区间", "2026-" in modal_txt, modal_txt[:150])
        import re as _re
        check("弹窗含减量幅度", _re.search(r"-\d+%", modal_txt) is not None, modal_txt[:200])
        check("弹窗含里程碑chip", "少抽" in modal_txt, modal_txt[:200])
        page.click(".cp-modal .cp-btn-primary")
        page.wait_for_timeout(400)
        check("弹窗可关闭", page.evaluate("window.appState.archiveView.show") is False, "")

        # -- 毕业挑战行图标语义 + 章卡 --
        grad_row = page.locator(".cp-ch-row", has_text="E2E毕业旅程")
        check("毕业挑战行存在", grad_row.count() == 1, str(grad_row.count()))
        end_icon = grad_row.locator(".cp-ch-row-end i").first.get_attribute("class")
        check("已结束挑战行尾是归档图标", end_icon and "fa-box-archive" in end_icon, str(end_icon))
        badge = grad_row.locator(".cp-ch-status").first
        check("毕业徽章不折行", badge.evaluate("el => getComputedStyle(el).whiteSpace") == "nowrap", "")

        # -- P0-B 毕业态即时渲染 --
        grad_row.click()
        page.wait_for_selector(".cp-grad-done", timeout=3000)
        grad_txt = page.inner_text(".cp-grad-done")
        check("毕业章卡渲染", "减量阶梯毕业" in grad_txt, grad_txt[:150])
        check("章卡阶梯叙事20到3", "20 根/天" in grad_txt and "3 根/天" in grad_txt, grad_txt[:200])
        check("章卡最后一程按钮", page.locator(".cp-grad-done button:has-text('最后一程')").count() == 1, "")

        # -- 浮点 fmt：活跃挑战 8→0 阶梯 daily target 非整数时 --
        page.evaluate(f"cpSelectChallenge('{cid_act}')")
        page.wait_for_selector(".cp-ch-titlebar", timeout=10000)
        page.wait_for_timeout(1500)
        body_txt = page.inner_text("body")
        has_long_float = "6.892307692307693" in body_txt or "7.878787878787878" in body_txt
        check("今日文案无16位浮点", not has_long_float, "")

        real_errors = [e for e in errors if "favicon" not in e]
        check("无页面JS错误", not real_errors, str(real_errors[:2]))
        browser.close()

    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM journey_archives WHERE user_id=?", (me_id or USER,))
    conn.commit()
    conn.close()
    for cid in (cid_grad, cid_act):
        try:
            api("DELETE", f"/challenges/{cid}?mode=purge", token=token)
        except Exception as e:
            print(f"  cleanup warn: purge {cid} :: {e}")
    print(f"\n=== 前2 旅程有终章 浏览器 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")


if __name__ == "__main__":
    main()
