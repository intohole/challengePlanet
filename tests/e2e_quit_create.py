#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = "/Users/intoblack/remoteWork/challengePlanet/static"
PORT = 8125

QUIT_CH = {
    "id": 50, "title": "戒烟挑战", "category": "quit", "status": "active",
    "task_type": "counter", "scene_template": "quit", "unit": "根",
    "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
    "goal_mode": "ceiling", "target_value": 20.0,
    "ladder_start": 20.0, "ladder_goal": 0.0, "ladder_interval": 1, "ladder_step": 1.0,
    "total_days": 42, "completed_days": 0, "streak": 0, "icon": "🚭",
    "color": "#ef4444", "today_checked": False, "decompose_mode": "none",
}

TODAY_D1 = {
    "date": "2026-09-15", "day_number": 1, "task_type": "counter",
    "task_title": "今日目标：控制在 20 根以内", "task_target": 20.0, "task_unit": "根",
    "today_cap": 20.0, "today_total": 0.0, "today_checkins": [],
    "goal_rule": "ladder", "direction": "decrease", "goal_type": "soft",
    "unit": "根", "remaining": 20.0, "settled": False, "checked_in": False,
    "progress_pct": 0, "repeatable": True, "sub_goals": [],
    "ladder_start": 20.0, "ladder_goal": 0.0, "ladder_interval": 1, "ladder_step": 1.0,
    "checkin_data": None, "period_target": 0, "week_total": 0, "has_record": False,
}

confirm_bodies: list[dict] = []


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
            send_json(self, 200, [QUIT_CH])
            return
        if path == "/api/v1/challenges/50/today":
            send_json(self, 200, TODAY_D1)
            return
        if path in ("/api/v1/challenges/50/checkins", "/api/v1/challenges/50/mercy", "/api/v1/challenges/50/weekly-report",
                    "/api/v1/challenges/50/adaptive/pending", "/api/v1/challenges/50/guidance"):
            send_json(self, 200, [])
            return
        if path in ("/api/v1/points/summary", "/api/v1/squads/my", "/api/portal/apps", "/api/v1/client/config"):
            send_json(self, 200, {})
            return
        send_json(self, 200, {})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/v1/challenges/confirm":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0))) if self.headers.get("Content-Length") else {}
            confirm_bodies.append(body)
            send_json(self, 200, {**QUIT_CH, "id": 99, "title": body.get("title", "")})
            return
        if path == "/api/v1/challenges/50/checkin":
            send_json(self, 200, {**TODAY_D1, "today_total": 1.0, "today_checkins": [{"id": 1, "value": 1, "unit": "根", "timestamp": "2026-09-15T10:00:00"}], "points_earned": 3, "checked_in": True})
            return
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
        page.on("console", lambda m: console_errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        print("== 1. 打开戒断场景创建面板 ==")
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(1500)
        page.evaluate("window.cpCreate.open()")
        page.wait_for_selector(".cp-modal-overlay", timeout=10000)
        page.locator(".cp-scene-card", has_text="戒断").click()
        page.wait_for_timeout(200)
        quit_panel = page.locator(".cp-diet-body", has_text="当前每天")
        check("quit 出现「当前每天/目标每天」面板", quit_panel.count() == 1)
        check("场景说明提示填当前每天", "当前每天" in page.locator(".cp-scene-note").inner_text())
        check("直接创建按钮默认禁用", page.locator(".cp-btn-direct").is_disabled())

        print("== 2. 填梯度 -> 直接创建 body 校验 ==")
        page.fill('input[placeholder="如 20"]', "20")
        page.wait_for_timeout(150)
        check("填入当前每天后直接创建可用", not page.locator(".cp-btn-direct").is_disabled())
        page.click(".cp-btn-direct")
        page.wait_for_timeout(800)
        check("确认接口已调用", len(confirm_bodies) == 1)
        if confirm_bodies:
            b = confirm_bodies[0]
            check("task_type=counter", b.get("task_type") == "counter", str(b.get("task_type")))
            check("direction=decrease", b.get("direction") == "decrease", str(b.get("direction")))
            check("goal_type=soft", b.get("goal_type") == "soft", str(b.get("goal_type")))
            check("goal_rule=ladder", b.get("goal_rule") == "ladder", str(b.get("goal_rule")))
            check("goal_mode=ceiling", b.get("goal_mode") == "ceiling", str(b.get("goal_mode")))
            check("unit=根", b.get("unit") == "根", str(b.get("unit")))
            check("ladder_start=20", b.get("ladder_start") == 20, str(b.get("ladder_start")))
            check("ladder_goal=0", b.get("ladder_goal") == 0, str(b.get("ladder_goal")))
            plan = b.get("plan", [])
            check("plan任务counter/根", plan and plan[0].get("task_type") == "counter" and plan[0].get("unit") == "根", str((plan or [{}])[0]))
        page.wait_for_timeout(800)
        page.click(".cp-modal-close", timeout=3000).__class__ if page.locator(".cp-modal-close").count() else None

        print("== 3. 关闭创建弹窗，展示戒烟挑战今日页(记账台) ==")
        page.evaluate("window.cpCreate.close()")
        page.wait_for_timeout(1200)
        page.text_content("#view-root") if False else None
        body_text = page.locator("body").inner_text()
        check("页面出现戒烟挑战", "戒烟挑战" in body_text)
        check("今日上限 20 根展示", "20" in body_text and "根" in body_text)
        check("出现「记一根」记账按钮", "记一根" in body_text, body_text[:200])
        check("不出现 binary 今日完成按钮", "今日完成" not in body_text and "今日已完成" not in body_text)
        shot_name = "quit_tally_desk.png"
        page.screenshot(path=os.path.join(ROOT, "../tests/browser_shots", shot_name), full_page=False)

        print("== 4. 点击记一根 v1 自动记账 ==")
        btn = page.locator("button", has_text="记一根").first
        btn.click()
        page.wait_for_timeout(800)
        body2 = page.locator("body").inner_text()
        check("记账后显示已记 1", "1" in body2 and "已记" in body2, body2[:120])

        errs = [e for e in console_errs if "favicon" not in e and "net::ERR" not in e]
        check("无JS控制台错误", not errs, "; ".join(errs[:3]))

        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
        server.shutdown()


if __name__ == "__main__":
    main()