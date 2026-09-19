#!/usr/bin/env python3
"""本地e2e: 预测节奏仪表盘渲染(已记/预计区间/触顶时刻/剩余额度/依据/阶梯终点/回测校准)"""
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = "/Users/intoblack/remoteWork/challengePlanet/static"
PORT = 8133

CH = {
    "id": 60, "title": "戒烟30天", "category": "quit", "status": "active",
    "task_type": "counter", "scene_template": "quit", "unit": "根",
    "direction": "decrease", "goal_rule": "ladder", "target_value": 8.0,
    "ladder_start": 20.0, "ladder_goal": 5.0,
    "total_days": 30, "completed_days": 12, "streak": 8, "icon": "🚭",
    "today_checked": False, "decompose_mode": "none",
}

FORECAST = {
    "enabled": True, "projected": 11.0,
    "confidence": 0.6, "confidence_label": "中", "basis": "按你最近两周的同时段节奏",
    "touch_at": "16:40", "remaining_hours": 2.5, "remaining_units": 4.0,
    "risk_level": 1, "coach_nudge": "", "nudge_level": 1,
    "reach_at": "", "calibrated": True, "bias": 1.5,
    "risk_window": "20:00-22:00",
    "risk_window_msg": "20:00-22:00 这段对你来说最难，多在「社交」场景，提前安排点别的",
    "risk_window_context": "社交",
    "context_pattern": "「压力」时你平均每天 6 根，是「家」的 3 倍",
    "ladder_outlook": {
        "on_track": False, "recent_avg": 18.0, "plan_cap": 15.0,
        "remaining_days": 18, "message": "最近7天平均 18 根，比阶梯计划高 3 根",
    },
}


CH2 = {
    "id": 61, "title": "喝水挑战", "category": "build", "status": "active",
    "task_type": "counter", "scene_template": "", "unit": "杯",
    "direction": "increase", "goal_rule": "fixed", "target_value": 8.0,
    "total_days": 21, "completed_days": 3, "streak": 3, "icon": "💧",
    "today_checked": False, "decompose_mode": "none",
}

FORECAST_INC = {
    "enabled": True, "projected": 9.0,
    "confidence": 0.6, "confidence_label": "中", "basis": "按你今天的记录速度",
    "touch_at": "", "remaining_hours": 0.0, "remaining_units": 5.0,
    "risk_level": 0, "coach_nudge": "", "nudge_level": 0,
    "reach_at": "21:30", "calibrated": False, "bias": 0.0, "ladder_outlook": None,
    "risk_window": "07:00-08:00",
    "risk_window_msg": "07:00-08:00 你通常状态最好，趁那会儿推进",
}


CH3 = {
    "id": 62, "title": "戒烟超限", "category": "quit", "status": "active",
    "task_type": "counter", "scene_template": "quit", "unit": "根",
    "direction": "decrease", "goal_rule": "ladder", "target_value": 20.0,
    "ladder_start": 20.0, "ladder_goal": 5.0,
    "total_days": 30, "completed_days": 13, "streak": 9, "icon": "🚭",
    "today_checked": True, "decompose_mode": "none",
}

FORECAST_OVER = {
    "enabled": True, "projected": 24.0,
    "confidence": 0.85, "confidence_label": "高", "basis": "按你最近两周的节奏",
    "touch_at": "", "remaining_hours": 0.0, "remaining_units": 0.0,
    "risk_level": 2, "coach_nudge": "今天已20根，超过目标了", "nudge_level": 2,
    "reach_at": "", "calibrated": False, "bias": 0.0, "ladder_outlook": None,
    "risk_window": "", "risk_window_msg": "", "risk_window_context": "", "context_pattern": "",
}


def send_json(handler, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            body = open(os.path.join(ROOT, "index.html"), "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            fp = os.path.normpath(os.path.join(ROOT, rel))
            if not fp.startswith(ROOT) or not os.path.isfile(fp):
                self.send_response(404)
                self.end_headers()
                return
            ctype = {".css": "text/css", ".js": "application/javascript", ".html": "text/html", ".svg": "image/svg+xml"}.get(os.path.splitext(fp)[1], "application/octet-stream")
            body = open(fp, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/v1/challenges":
            send_json(self, 200, [CH, CH2, CH3])
            return
        if path == "/api/v1/challenges/60/today":
            send_json(self, 200, {"date": "2026-09-19", "day_number": 13, "task_type": "counter",
                                  "task_title": "今日上限 8 根", "task_target": 8, "today_total": 4,
                                  "today_target": 8, "today_cap": 8, "goal_rule": "ladder",
                                  "direction": "decrease", "unit": "根", "remaining": 4,
                                  "settled": False, "checked_in": False, "progress_pct": 40,
                                  "repeatable": True, "sub_goals": [], "forecast": FORECAST})
            return
        if path == "/api/v1/challenges/61/today":
            send_json(self, 200, {"date": "2026-09-19", "day_number": 4, "task_type": "counter",
                                  "task_title": "今日喝水 8 杯", "task_target": 8, "today_total": 3,
                                  "today_target": 8, "today_cap": 8, "goal_rule": "fixed",
                                  "direction": "increase", "unit": "杯", "remaining": 5,
                                  "settled": False, "checked_in": False, "progress_pct": 38,
                                  "repeatable": True, "sub_goals": [], "forecast": FORECAST_INC})
            return
        if path == "/api/v1/challenges/62/today":
            send_json(self, 200, {"date": "2026-09-19", "day_number": 13, "task_type": "counter",
                                  "task_title": "今日上限 18 根", "task_target": 18, "today_total": 20,
                                  "today_target": 18, "today_cap": 18, "goal_rule": "ladder",
                                  "direction": "decrease", "unit": "根", "remaining": 0,
                                  "settled": False, "checked_in": True, "progress_pct": 100,
                                  "repeatable": True, "sub_goals": [], "forecast": FORECAST_OVER})
            return
        if path in ("/api/v1/challenges/60/checkins", "/api/v1/challenges/61/checkins",
                    "/api/v1/challenges/62/checkins",
                    "/api/v1/challenges/60/mercy", "/api/v1/challenges/61/mercy",
                    "/api/v1/challenges/62/mercy",
                    "/api/v1/challenges/60/adaptive/pending", "/api/v1/challenges/61/adaptive/pending",
                    "/api/v1/challenges/62/adaptive/pending",
                    "/api/v1/challenges/60/guidance", "/api/v1/challenges/61/guidance",
                    "/api/v1/challenges/62/guidance",
                    "/api/v1/challenges/60/weekly-report", "/api/v1/challenges/61/weekly-report",
                    "/api/v1/challenges/62/weekly-report"):
            send_json(self, 200, [])
            return
        if path in ("/api/v1/points/summary", "/api/v1/squads/my", "/api/portal/apps", "/api/v1/client/config"):
            send_json(self, 200, {})
            return
        send_json(self, 200, {})

    def do_POST(self):
        send_json(self, 200, {})


server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844})
        ctx.add_init_script("localStorage.setItem('uc_access_token','e2e-token');")
        page = ctx.new_page()
        console_errs: list[str] = []
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        print("== 1. 首页渲染节奏仪表盘 ==")
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(2000)
        body = page.locator("body").inner_text()
        check("展示已记 4", "4" in body)
        check("展示预计 11", "11" in body)
        check("无±工程记法", "±" not in body)
        check("无浮点垃圾小数", "000000" not in body)
        check("展示触顶 16:40", "16:40" in body)
        check("展示还可 4", "还可" in body)
        check("展示黄灯状态(预计会超)", "预计会超" in body)
        check("展示严厉提示(收住)", "现在收住还来得及" in body)
        check("展示依据文案", "同时段节奏" in body)
        check("展示回测校准", "已校准" in body)
        check("展示阶梯计划对比", "比阶梯计划高" in body)
        check("不再出现看不懂的'离目标还差'", "离目标还差" not in body)
        check("展示前瞻风险窗口", "对你来说最难" in body)
        check("展示情境归因", "社交" in body)
        check("展示条件模式", "3 倍" in body)

        rail = page.locator(".cp-rail")
        check("节奏轨存在(签名元素)", rail.count() >= 1)
        check("节奏轨有预计标记", page.locator(".cp-rail-proj").count() >= 1)
        check("节奏轨有上限刻度", page.locator(".cp-rail-cap").count() >= 1)
        check("节奏轨可访问标签", "预计" in (rail.first.get_attribute("aria-label") or ""))
        check("无重复进度条(ladder只有节奏轨)", page.locator(".cp-task-progress").count() == 0)

        overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check("无横向溢出(375宽)", overflow <= 1, str(overflow))
        bounds = page.evaluate("""() => {
          const t = document.querySelector('.cp-rail-track')
          const p = document.querySelector('.cp-rail-proj')
          if (!t || !p) return null
          const tr = t.getBoundingClientRect(), pr = p.getBoundingClientRect()
          return { inTrack: pr.left >= tr.left - 6 && pr.right <= tr.right + 6,
                   fillW: document.querySelector('.cp-rail-fill').getBoundingClientRect().width }
        }""")
        check("预计标记在轨内", bool(bounds) and bounds["inTrack"], str(bounds))
        check("已记填充宽度>0", bool(bounds) and bounds["fillW"] > 0, str(bounds))

        status = page.locator(".cp-dash-status")
        check("红黄绿状态徽章存在", status.count() >= 1)
        check("状态徽章为黄灯", status.first.get_attribute("class").find("warn") >= 0, status.first.get_attribute("class"))
        warn_color = page.evaluate("""() => {
          const s = document.querySelector('.cp-dash-status')
          return s ? getComputedStyle(s).color : ''
        }""")
        check("黄灯配色正确", "245, 158, 11" in warn_color, warn_color)

        dash = page.locator(".cp-dash")
        check("仪表盘容器存在", dash.count() >= 1)
        dash_text = dash.first.inner_text().replace("\n", " | ")
        print("  [渲染文本] " + dash_text)
        check("预计为单个数字(无左右)", "左右" not in dash_text and "预计" in dash_text, dash_text)
        check("无多余小数", ".0" not in dash_text and ".1" not in dash_text, dash_text)
        cell_text = page.locator(".cp-dash-cell").all_inner_texts()
        check("至少4个指标格", len(cell_text) >= 4, str(cell_text))

        print("== 2. 切换到增加型挑战(喝水) 渲染达标时刻 ==")
        page.locator(".cp-ch-chip", has_text="喝水挑战").click()
        page.wait_for_timeout(1200)
        body2 = page.locator("body").inner_text()
        check("展示已记 3 / 8", "3" in body2 and "8" in body2)
        check("展示预计达标 21:30", "21:30" in body2)
        check("展示依据文案 今日速度", "记录速度" in body2)
        check("展示前瞻最佳时段", "状态最好" in body2)

        page.screenshot(path="/tmp/cp_forecast_dash.png", full_page=False)

        print("== 3. 已超上限 危险态渲染红色 ==")
        page.locator(".cp-ch-chip", has_text="戒烟超限").click()
        page.wait_for_timeout(1200)
        body3 = page.locator("body").inner_text()
        check("展示红灯状态(已超计划)", "已超计划" in body3)
        check("展示严厉文案(停下来)", "停下来，别再继续了" in body3)
        check("已超时隐藏前瞻窗口", "对你来说最难" not in body3)
        over_status = page.evaluate("""() => {
          const s = document.querySelector('.cp-dash-status')
          return s ? getComputedStyle(s).color : ''
        }""")
        check("红灯配色正确", "239, 68, 68" in over_status, over_status)
        over_color = page.evaluate("""() => {
          const f = document.querySelector('.cp-rail-fill')
          return f ? getComputedStyle(f).backgroundColor : ''
        }""")
        check("节奏轨填充为红色", "rgb(239, 68, 68)" in over_color, over_color)

        errs = [e for e in console_errs if "favicon" not in e and "net::ERR" not in e]
        check("无JS控制台错误", not errs, "; ".join(errs[:3]))

        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
        server.shutdown()


if __name__ == "__main__":
    main()
