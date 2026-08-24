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


def shot(page, name: str) -> None:
    try:
        page.screenshot(path=os.path.join(OUT, name), full_page=False)
    except Exception:
        pass


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


def start_server() -> tuple[str, ThreadingHTTPServer]:
    handler = partial(Handler)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return f"http://127.0.0.1:{port}", httpd


TODAY = "2026-08-25"

MOCK = {
    "/api/v1/challenges": {
        "data": [
            {"id": 1, "title": "21天每天阅读30分钟", "icon": "📖", "status": "active", "category": "learn",
             "task_type": "counter", "unit": "页", "total_days": 21, "completed_days": 5, "streak": 3,
             "start_date": "2026-08-01", "share_token": "tok1", "target_value": 30,
             "decompose_mode": "time_slot", "ai_plan": []},
            {"id": 2, "title": "戒烟挑战", "icon": "🚭", "status": "active", "category": "quit",
             "task_type": "binary", "unit": "次", "total_days": 42, "completed_days": 0, "streak": 0,
             "start_date": "2026-08-25", "share_token": "tok2", "target_value": 0, "ai_plan": []},
        ]
    },
    "/api/v1/challenges/1/today": {
        "data": {
            "day_number": 6, "date": TODAY, "task_title": "连续阅读30分钟，记录你的专注时段",
            "task_description": "今天继续 30 分钟阅读，尝试在精力最好的时段完成。",
            "task_type": "counter", "task_target": 30, "task_unit": "页", "unit": "页",
            "progress_pct": 66, "repeatable": True, "today_total": 20, "today_target": 30,
            "checked_in": True,
            "checkin_data": {"declaration": "今天也要坚持读完 30 页", "ai_feedback": "你今天在晚高峰时段表现不错"},
            "sub_goals": [
                {"id": 11, "title": "晨间阅读", "time_window_start": "06:00", "time_window_end": "09:00",
                 "today_value": 10, "target_value": 10, "progress_pct": 100},
                {"id": 12, "title": "晚间阅读", "time_window_start": "20:00", "time_window_end": "23:00",
                 "today_value": 10, "target_value": 20, "progress_pct": 50},
            ],
            "goal_rule": "ladder", "today_cap": 30, "remaining": 10,
            "task_tip": "读累了就休息 5 分钟再继续", "task_steps": ["翻开书", "读 10 分钟", "记录心得"],
            "dynamic_baseline": 0,
            "today_checkins": [
                {"timestamp": TODAY + "T08:12:00", "value": 10, "unit": "页", "sub_goal_id": 11, "mood": "good",
                 "reflection": "晨间效率很高", "target_value": 10, "goal_type": "hard"},
                {"timestamp": TODAY + "T21:30:00", "value": 10, "unit": "页", "sub_goal_id": 12, "mood": "normal",
                 "reflection": "", "target_value": 20, "goal_type": "soft"},
            ],
        }
    },
    "/api/v1/challenges/1/checkins": {"data": []},
    "/api/v1/challenges/1/mercy": {"data": {"missed_dates": []}},
    "/api/v1/challenges/1/weekly-report": {"data": {"content": "本周你完成了 5/7 天打卡，晨间时段表现最佳。", "week_checkins": 5, "week_days": 7}},
    "/api/v1/points/summary": {"data": {"points": 128, "level": 3}},
    "/api/v1/challenges/1/adaptive/pending": {"data": {"suggestion": None}},
    "/api/v1/challenges/1/guidance": {
        "data": {
            "phase_name": "巩固期", "phase_range": "第8-14天", "phase_color": "#D97706", "phase_icon": "🌱",
            "encouragement": "你已经走过适应期，节奏正在成型。",
            "phase_desc": "本周是巩固节奏的关键阶段。", "phase_tip": "固定时段打卡，成功率更高。",
            "completed_days": 5, "is_at_risk": False,
            "next_milestone": {"day": 7, "days_to_go": 2, "tip": "坚持到第 7 天就完成首个里程碑"},
            "companion": None,
        }
    },
    "/api/v1/challenges/1/report/hourly": {
        "data": {
            "items": [{"hour": h, "total_value": (12 if h == 8 else 8 if h == 21 else 4 if h in (7, 9, 20, 22) else 0)} for h in range(24)],
            "peak_hour": 8, "peak_value": 12, "insight": "你的高效时段集中在早上，继续保持。",
        }
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
    hit = None
    for k, v in MOCK.items():
        if url.endswith(k):
            hit = v
            break
    if hit is None:
        route.fulfill(status=200, content_type="application/json", body=json.dumps({"data": None}))
        return
    route.fulfill(status=200, content_type="application/json", body=json.dumps(hit))


def main() -> None:
    base, httpd = start_server()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, ignore_https_errors=True)
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        page.add_init_script(
            "localStorage.setItem('uc_access_token','mock-token');"
            "localStorage.setItem('uc_refresh_token','mock-r');"
            "localStorage.setItem('cp_user_id','1');localStorage.setItem('cp_nickname','E2E测试');"
        )
        page.route("**/api/v1/**", route_mock)

        print("== 1. 加载首页 ==")
        page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector(".cp-tabs", timeout=45000)
        page.wait_for_selector(".cp-task-card", timeout=15000)
        page.wait_for_timeout(1500)
        shot(page, "tabs_1_today.png")

        tabs = page.query_selector_all(".cp-tab span")
        tab_txt = [t.inner_text() for t in tabs]
        print("  tabs:", tab_txt)
        check("三Tab渲染(今日/进度/洞察)", tab_txt == ["今日", "进度", "洞察"], str(tab_txt))
        active = page.query_selector(".cp-tab.active span")
        check("默认Tab=今日", active is not None and active.inner_text() == "今日", active.inner_text() if active else "")

        titlebar = page.query_selector(".cp-ch-titlebar")
        tb_text = titlebar.inner_text() if titlebar else ""
        check("标题栏含挑战标题", titlebar is not None and "阅读30分钟" in tb_text, tb_text[:80])
        check("标题栏含进度天数", "5/21" in tb_text, tb_text[:80])
        check("标题栏伴学按钮", page.query_selector(".cp-hero-companion-btn") is not None, "")

        task_title = page.query_selector(".cp-task-title")
        check("今日任务卡渲染", task_title is not None and "阅读30分钟" in task_title.inner_text(), "")
        timeline = page.query_selector(".cp-timeline")
        check("今日时间线渲染", timeline is not None, "")
        check("时间线已移除每条AI反馈", page.query_selector(".cp-timeline-feedback") is None, "")
        tl_items = page.query_selector_all(".cp-timeline-item")
        check("时间线含2条记录", len(tl_items) == 2, f"items={len(tl_items)}")
        check("时间线含心情", page.query_selector(".cp-timeline-mood") is not None, "")

        print("== 2. 切换进度Tab ==")
        page.click(".cp-tab:has-text('进度')")
        page.wait_for_selector(".cp-progress-card", timeout=10000)
        page.wait_for_timeout(2500)
        shot(page, "tabs_2_progress.png")
        active = page.query_selector(".cp-tab.active span")
        check("切换至进度Tab", active is not None and active.inner_text() == "进度", "")
        check("进度卡渲染", page.query_selector(".cp-progress-card") is not None, "")
        check("数据报表渲染", page.query_selector(".cp-report-quickgrid") is not None, "")
        check("近7天节奏容器渲染", page.query_selector(".cp-today-viz") is not None, "")
        page.wait_for_selector("#cp-mini-hourly-1 .cp-mini-bar", timeout=10000)
        bars = page.query_selector_all("#cp-mini-hourly-1 .cp-mini-bar")
        check("时段条渲染", len(bars) >= 12, f"bars={len(bars)}")

        print("== 3. 切换洞察Tab ==")
        page.click(".cp-tab:has-text('洞察')")
        page.wait_for_selector(".cp-guidance-card", timeout=10000)
        page.wait_for_timeout(1200)
        shot(page, "tabs_3_insight.png")
        active = page.query_selector(".cp-tab.active span")
        check("切换至洞察Tab", active is not None and active.inner_text() == "洞察", "")
        check("本周洞察渲染", page.query_selector(".cp-weekly-md") is not None, "")
        check("引导卡渲染", page.query_selector(".cp-guidance-card") is not None, "")
        check("里程碑渲染", page.query_selector(".cp-milestone") is not None, "")
        check("无行业参考数据", page.query_selector(".cp-benchmark") is None, "")
        check("无percentile", page.query_selector(".cp-percentile") is None, "")
        check("无场景徽章", page.query_selector(".cp-hero-scene") is None, "")

        print("== 4. 回到今日Tab ==")
        page.click(".cp-tab:has-text('今日')")
        page.wait_for_selector(".cp-task-card", timeout=10000)
        active = page.query_selector(".cp-tab.active span")
        check("切回今日Tab", active is not None and active.inner_text() == "今日", "")
        check("FAB仍在", page.query_selector(".cp-fab") is not None, "")

        body_text = page.evaluate("() => document.body.innerText")
        check("页面无行业参考字样", "行业" not in body_text and "超越" not in body_text, "")

        browser.close()

    httpd.shutdown()
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
