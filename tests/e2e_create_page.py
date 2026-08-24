#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = "/Users/intoblack/remoteWork/challengePlanet/static"
PORT = 8124

plan = []
for d in range(1, 67):
    diff = 1 if d <= 10 else 2 if d <= 20 else 3 if d <= 35 else 4 if d <= 50 else 5
    plan.append({
        "day": d,
        "title": "跑步 " + str(2 + (d - 1) // 10) + " 公里 · 第" + str(d) + "天",
        "description": "保持匀速呼吸，注意落地轻盈",
        "difficulty": diff,
        "target_value": 2 + (d - 1) // 10,
        "unit": "公里",
    })

PARSED = {
    "title": "42天从零到5公里",
    "category": "fitness",
    "duration_days": 66,
    "description": "每天跑步逐渐加量",
    "task_type": "counter",
    "target_value": 3.0,
    "unit": "公里",
    "direction": "increase",
    "goal_type": "hard",
    "decompose_mode": "none",
    "slot_hours": 1,
    "slot_target_value": 0.0,
    "goal_rule": "ladder",
    "ladder_start": 2.0,
    "ladder_goal": 8.0,
    "ladder_interval": 3,
    "ladder_step": 1,
}


def sse(obj: dict) -> str:
    return "data: " + json.dumps(obj, ensure_ascii=False) + "\n\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, code: int, obj) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(ROOT, "index.html"), "rb") as f:
                body = f.read()
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
            ext = os.path.splitext(fp)[1]
            ctype = {
                ".css": "text/css",
                ".js": "application/javascript",
                ".html": "text/html",
                ".svg": "image/svg+xml",
            }.get(ext, "application/octet-stream")
            with open(fp, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/api/v1/challenges":
            self._send_json(200, {"items": []})
            return
        if path == "/api/v1/points/summary":
            self._send_json(200, {"total_points": 0})
            return
        if path == "/api/v1/squads/my":
            self._send_json(200, [])
            return
        if path == "/api/portal/apps":
            self._send_json(200, [])
            return
        if path.startswith("/api/v1/"):
            self._send_json(200, {})
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/v1/challenges/nl-create":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            w = self.wfile
            w.write(sse({"type": "parsing"}).encode("utf-8"))
            w.flush()
            time.sleep(0.15)
            w.write(sse({"type": "parsed", "parsed": PARSED}).encode("utf-8"))
            w.flush()
            time.sleep(0.15)
            plan_text = json.dumps(plan, ensure_ascii=False)
            last_day = 0
            for i in range(0, len(plan_text), 24):
                chunk = plan_text[i:i + 24]
                w.write(sse({"type": "token", "token": chunk}).encode("utf-8"))
                w.flush()
                time.sleep(0.012)
                hits = [int(m) for m in re.findall(r'"day"\s*:\s*(\d+)', plan_text[:i + 24])]
                if hits:
                    cur = max(hits)
                    if cur != last_day:
                        last_day = cur
                        w.write(sse({"type": "day", "day": cur, "total": 66}).encode("utf-8"))
                        w.flush()
            w.write(sse({
                "type": "preview",
                "parsed": PARSED,
                "plan": plan,
                "suggestions": ["保持匀速", "注意拉伸"],
            }).encode("utf-8"))
            w.flush()
            return
        if path == "/api/v1/challenges/confirm":
            self._send_json(200, {"id": 999, "title": "42天从零到5公里"})
            return
        if path.startswith("/api/v1/"):
            self._send_json(200, {})
            return
        self._send_json(404, {"error": "not found"})


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
        failed_resp: list[str] = []
        page.on("response", lambda r: failed_resp.append(r.url) if r.status >= 400 else None)

        print("== 1. 打开创建弹窗 ==")
        page.goto(f"http://127.0.0.1:{PORT}/", wait_until="networkidle", timeout=60000)
        page.wait_for_selector("#view-root", timeout=30000)
        page.wait_for_timeout(1200)
        page.evaluate("window.cpCreate.open()")
        page.wait_for_selector(".cp-modal-overlay", timeout=10000)
        cards = page.locator(".cp-scene-card")
        check("场景卡数量=11", cards.count() == 11, str(cards.count()))
        check("初始无场景说明", page.locator(".cp-scene-note").count() == 0)

        print("== 2. 场景选中说明 + 示例chips ==")
        page.locator(".cp-scene-card", has_text="健身").click()
        page.wait_for_timeout(200)
        note = page.locator(".cp-scene-note")
        check("选中后出现场景说明", note.count() == 1)
        if note.count():
            check("场景说明含价值描述", "力量与有氧" in note.inner_text(), note.inner_text())
        chips = page.locator(".cp-sample-chip")
        check("示例chips出现", chips.count() >= 2, str(chips.count()))
        if chips.count():
            first = chips.first.inner_text()
            chips.first.click()
            page.wait_for_timeout(150)
            val = page.locator("textarea.cp-field").input_value()
            check("点击示例填入描述框", val == first, f"{val!r} != {first!r}")

        print("== 3. AI生成 -> planning实时标题 ==")
        page.locator("button", has_text="AI生成计划").click()
        page.wait_for_selector(".cp-gen-task", timeout=15000)
        gen_task = page.locator(".cp-gen-task").first.inner_text()
        check("planning实时任务标题出现", "天" in gen_task or "设计" in gen_task, gen_task)
        print("   实时标题:", gen_task)

        print("== 4. preview 玩法总览卡 + 难度曲线 ==")
        page.wait_for_selector(".cp-play-card", timeout=30000)
        play = page.locator(".cp-play-card").first.inner_text()
        check("玩法卡类型(计数打卡)", "计数打卡" in play, play)
        check("玩法卡目标(每日3公里)", "3" in play and "公里" in play, play)
        check("玩法卡方向(目标逐日递增)", "逐日递增" in play, play)
        curve = page.locator(".cp-curve-svg")
        check("难度曲线SVG渲染", curve.count() == 1)
        labels = page.locator(".cp-phase-labels").first.inner_text()
        for lbl in ["适应期", "巩固期", "维持期"]:
            check(f"阶段标注含{lbl}", lbl in labels, labels)

        print("== 5. 计划折叠 ==")
        page.wait_for_timeout(300)
        day_count = page.locator(".cp-plan-day").count()
        check("折叠态天数<66", 0 < day_count < 66, str(day_count))
        toggle = page.locator(".cp-plan-toggle")
        check("折叠按钮出现", toggle.count() == 1)
        if toggle.count():
            ttext = toggle.first.inner_text()
            check("按钮显示展开全部+66天", "展开全部" in ttext and "66" in ttext, ttext)
            toggle.first.click()
            page.wait_for_timeout(300)
            expanded = page.locator(".cp-plan-day").count()
            check("展开后显示全部66天", expanded == 66, str(expanded))
            toggle.first.click()
            page.wait_for_timeout(200)
            collapsed2 = page.locator(".cp-plan-day").count()
            check("再次折叠恢复", collapsed2 == day_count, str(collapsed2))

        print("== 6. 创建后toast引导 ==")
        page.locator("button", has_text="开启挑战").click()
        page.wait_for_selector(".cp-toast", timeout=10000)
        toast = page.locator(".cp-toast").inner_text()
        check("toast显示第1天任务", "第1天" in toast, toast)
        print("   toast:", toast)

        errs = [e for e in console_errs if "favicon" not in e and "net::ERR" not in e]
        check("无JS控制台错误", not errs, "; ".join(errs[:3]))
        non_fav = [u for u in failed_resp if "favicon" not in u]
        check("无4xx/5xx资源", not non_fav, "; ".join(non_fav[:5]))

        page.screenshot(path="/tmp/cp_create_preview.png", full_page=False)
        print("\n=== 结果 ===")
        for f in failed:
            print("  FAILED:", f)
        print(f"PASS {len(passed)} / {len(passed) + len(failed)}")
        server.shutdown()


if __name__ == "__main__":
    main()
