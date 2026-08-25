#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")

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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=STATIC, **kw)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/" or path == "":
            self.path = "/index.html"
        elif path.startswith("/static/"):
            self.path = path[len("/static"):]
        else:
            self.send_error(404)
            return
        super().do_GET()

    def log_message(self, *a):
        pass


def start_server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler))
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{port}", httpd


TODAY = "2026-08-25"

MOCK = {
    "/api/v1/challenges": {
        "data": [
            {"id": 1, "title": "21天每天阅读30分钟", "icon": "📖", "status": "active", "category": "learn",
             "task_type": "counter", "unit": "页", "total_days": 21, "completed_days": 5, "streak": 3,
             "start_date": "2026-08-01", "share_token": "tok1", "target_value": 30,
             "decompose_mode": "none", "ai_plan": []},
            {"id": 2, "title": "戒烟挑战", "icon": "🚭", "status": "active", "category": "quit",
             "task_type": "binary", "unit": "次", "total_days": 42, "completed_days": 0, "streak": 0,
             "start_date": "2026-08-25", "share_token": "tok2", "target_value": 0, "ai_plan": []},
        ]
    },
    "/api/v1/challenges/1/today": {
        "data": {
            "day_number": 6, "date": TODAY, "task_title": "连续阅读30分钟，记录你的专注时段",
            "task_description": "今天继续 30 分钟阅读。", "task_type": "counter", "task_target": 30,
            "task_unit": "页", "unit": "页", "progress_pct": 66, "repeatable": True,
            "today_total": 20, "today_target": 30, "checked_in": False,
            "checkin_data": None, "sub_goals": [], "goal_rule": "fixed", "today_cap": 30,
            "remaining": 10, "task_tip": "", "task_steps": [], "dynamic_baseline": 0,
            "today_checkins": [],
        }
    },
    "/api/v1/challenges/1/checkins": {"data": []},
    "/api/v1/challenges/1/mercy": {"data": {"missed_dates": []}},
    "/api/v1/challenges/1/weekly-report": {"data": None},
    "/api/v1/points/summary": {"data": {"total": 128, "week_points": 20}},
    "/api/v1/challenges/1/adaptive/pending": {"data": {"suggestion": None}},
    "/api/v1/challenges/1/guidance": {
        "data": {"is_at_risk": False, "phase_name": "巩固期", "phase_range": "第8-14天",
                 "phase_color": "#D97706", "phase_icon": "🌱", "encouragement": "节奏正在成型。",
                 "phase_desc": "本周是巩固节奏的关键阶段。", "phase_tip": "固定时段打卡，成功率更高。",
                 "completed_days": 5, "next_milestone": None, "companion": None}
    },
    "/api/v1/challenges/2/today": {"data": None},
    "/api/v1/challenges/2/checkins": {"data": []},
    "/api/v1/challenges/2/mercy": {"data": {"missed_dates": []}},
    "/api/v1/challenges/2/weekly-report": {"data": None},
    "/api/v1/challenges/2/adaptive/pending": {"data": {"suggestion": None}},
    "/api/v1/challenges/2/guidance": {"data": None},
}


def route_mock(route, req) -> None:
    url = req.url.split("?")[0]
    if req.method == "DELETE" and "/challenges/" in url:
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"deleted": True, "status": "ended", "message": "挑战已结束，战绩已保留"}))
        return
    hit = None
    for k, v in MOCK.items():
        if url.endswith(k):
            hit = v
            break
    body = json.dumps(hit if hit is not None else {"data": None})
    route.fulfill(status=200, content_type="application/json", body=body)


def main() -> None:
    base, httpd = start_server()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 844}, ignore_https_errors=True)
        console_errs: list[str] = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))
        page.add_init_script(
            "localStorage.setItem('uc_access_token','mock-token');"
            "localStorage.setItem('uc_refresh_token','mock-r');"
            "localStorage.setItem('cp_user_id','1');localStorage.setItem('cp_nickname','E2E测试');"
        )
        page.route("**/api/v1/**", route_mock)

        print("== 1. 打卡卡片上移至顶部 ==")
        page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-task-card", timeout=45000)
        page.wait_for_timeout(1200)
        task = page.query_selector(".cp-task-card")
        tabs = page.query_selector(".cp-tabs")
        task_y = task.bounding_box()["y"]
        tabs_y = tabs.bounding_box()["y"]
        print(f"  task-card y={task_y}, tabs y={tabs_y}")
        check("打卡卡片在Tab之上", task_y < tabs_y, f"task={task_y} tabs={tabs_y}")
        check("打卡卡片在首屏高度内", task_y < 844, f"task_y={task_y}")
        check("打卡操作控件可见", page.query_selector(".cp-big-tap, .cp-checkin-box") is not None, "")

        print("== 2. 切换进度Tab打卡卡仍在顶部 ==")
        page.click(".cp-tab:has-text('进度')")
        page.wait_for_selector(".cp-progress-card", timeout=10000)
        page.wait_for_timeout(800)
        task2 = page.query_selector(".cp-task-card")
        tabs2 = page.query_selector(".cp-tabs")
        check("进度Tab下打卡卡仍在Tab之上",
              task2 is not None and task2.bounding_box()["y"] < tabs2.bounding_box()["y"], "")

        print("== 3. 我的页 结束/删除入口 ==")
        page.click(".cp-bottom-nav button:has-text('我的')")
        page.wait_for_selector(".cp-ch-row", timeout=10000)
        page.wait_for_timeout(800)
        rows = page.query_selector_all(".cp-ch-row")
        end_btns = page.query_selector_all(".cp-ch-row-end")
        check("挑战行渲染", len(rows) == 2, f"rows={len(rows)}")
        check("每行都有结束/删除入口", len(end_btns) == 2, f"end_btns={len(end_btns)}")
        icons = [b.query_selector("i").get_attribute("class") for b in end_btns]
        print("  end-icons:", icons)
        check("有记录行=旗子图标(结束)", "fa-flag-checkered" in icons[0], tr(icons))
        check("无记录行=垃圾桶图标(删除)", "trash" in icons[1], tr(icons))

        print("== 4. 点击结束按钮触发删除API与toast ==")
        dialogs: list[str] = []
        page.on("dialog", lambda d: (dialogs.append(d.message or "") or d.accept()))
        end_btns[0].click()
        page.wait_for_timeout(800)
        toast = page.query_selector(".cp-toast")
        check("点击后弹出确认框", len(dialogs) == 1, str(dialogs))
        check("确认框文案明确", "结束该挑战" in dialogs[0], dialogs[0])
        page.wait_for_selector(".cp-toast", timeout=5000)
        check("操作成功toast", toast is not None and "已结束挑战" in (toast.inner_text() or ""), "")

        browser.close()

    httpd.shutdown()
    print("\n===== 汇总 =====")
    print(f"通过 {len(passed)} 项, 失败 {len(failed)} 项")
    for name, d in failed:
        print(f"  FAILED: {name} :: {d}")
    if console_errs:
        print("\n控制台错误(前10条):")
        for e in console_errs[:10]:
            print("  -", e[:160])
    else:
        print("\n无控制台错误")
    raise SystemExit(1 if failed else 0)


def tr(items) -> str:
    return str(items)


if __name__ == "__main__":
    main()