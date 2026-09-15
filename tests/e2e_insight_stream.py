#!/usr/bin/env python3
"""本地e2e: 洞察按需触发(进入页面不跑weekly/切洞察tab才写流式生成+重新生成)"""
from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = "/Users/intoblack/remoteWork/challengePlanet/static"
PORT = 8126

CH = {
    "id": 50, "title": "每周跑步挑战", "category": "fitness", "status": "active",
    "task_type": "counter", "scene_template": "running", "unit": "公里",
    "direction": "increase", "goal_rule": "fixed", "target_value": 3.0,
    "total_days": 21, "completed_days": 2, "streak": 1, "icon": "🏃",
    "today_checked": False, "decompose_mode": "none",
}

requests_log: list[str] = []
insight_bodies: list[dict] = []
insight_hits = {"count": 0}


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

    def _record(self):
        path = self.path.split("?")[0]
        requests_log.append(path)

    def do_GET(self):
        self._record()
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
            send_json(self, 200, [CH])
            return
        if path == "/api/v1/challenges/50/today":
            send_json(self, 200, {"date": "2026-09-15", "day_number": 1, "task_type": "counter",
                                  "task_title": "今日跑步 3 公里", "task_target": 3, "today_total": 0,
                                  "today_checkins": [], "goal_rule": "fixed", "direction": "increase",
                                  "settled": False, "checked_in": False, "progress_pct": 0,
                                  "repeatable": True, "sub_goals": [], "units": "公里"})
            return
        if path == "/api/v1/challenges/50/weekly-report":
            send_json(self, 200, {"report": "", "week_checkins": 0, "week_days": 7})
            return
        if path in ("/api/v1/challenges/50/checkins", "/api/v1/challenges/50/mercy",
                    "/api/v1/challenges/50/adaptive/pending", "/api/v1/challenges/50/guidance"):
            send_json(self, 200, [])
            return
        if path in ("/api/v1/points/summary", "/api/v1/squads/my", "/api/portal/apps", "/api/v1/client/config"):
            send_json(self, 200, {})
            return
        send_json(self, 200, {})

    def do_POST(self):
        self._record()
        path = self.path.split("?")[0]
        if path == "/api/v1/challenges/50/insight/stream":
            insight_hits["count"] += 1
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0))) if self.headers.get("Content-Length") else {}
            insight_bodies.append(body)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            w = self.wfile
            for token in ["本周记录 2/21 天，", "节奏稳步推进；", "建议固定在晨间跑步。"]:
                time.sleep(0.15)
                w.write(("data: " + json.dumps({"type": "token", "token": token}, ensure_ascii=False) + "\n\n").encode())
                w.flush()
            w.write(("data: " + json.dumps({"type": "done", "content": "本周记录 2/21 天，节奏稳步推进；建议固定在晨间跑步。"}, ensure_ascii=False) + "\n\n").encode())
            w.flush()
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
        page.on("pageerror", lambda e: console_errs.append(str(e)))

        print("== 1. 进入页面(今日tab) 不请求 weekly 洞察 ==")
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(2000)
        check("进入页面未请求 /weekly-report", "/api/v1/challenges/50/weekly-report" not in requests_log)
        check("进入页面未请求 /insight/stream", insight_hits["count"] == 0)

        print("== 2. 切到洞察 tab 自动触发流式生成 ==")
        page.locator(".cp-tab", has_text="洞察").click()
        page.wait_for_timeout(800)
        check("切洞察 tab 触发 insight/stream", insight_hits["count"] == 1)
        check("stream body force=false", insight_bodies and insight_bodies[0].get("force") is False)

        print("== 3. 流式完成后展示洞察全文 + 重新生成按钮 ==")
        page.wait_for_selector(".cp-weekly-md", timeout=15000)
        body = page.locator("body").inner_text()
        check("展示全文(含第三条)", "晨间跑步" in body)
        check("出现重新生成按钮", "重新生成" in body)

        print("== 4. 重新生成 -> 再次触发流式(force=true) ==")
        page.locator("button", has_text="重新生成").click()
        page.wait_for_timeout(400)
        check("重新生成再次触发 request", insight_hits["count"] == 2)
        check("重新生成 body force=true", insight_bodies and insight_bodies[1].get("force") is True)

        page.screenshot(path="/tmp/cp_insight_stream.png", full_page=False)
        errs = [e for e in console_errs if "favicon" not in e and "net::ERR" not in e]
        check("无JS控制台错误", not errs, "; ".join(errs[:3]))

        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
        server.shutdown()


if __name__ == "__main__":
    main()