#!/usr/bin/env python3
# 体重控制打卡 · 前端视图渲染测试
# 复用仓库既有 browser-mock 结构，仅验证 diet 视图在真实静态页上的 DOM 渲染与绑定。
from __future__ import annotations

import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC = os.path.join(ROOT, "static")
TODAY = "2026-08-25"
TARGET = 1905

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


MOCK = {
    "/api/v1/challenges": {"data": [
        {"id": 1, "title": "30天减重3公斤", "icon": "⚖️", "status": "active", "category": "fitness",
         "task_type": "diet", "unit": "千卡", "total_days": 30, "completed_days": 2, "streak": 2,
         "start_date": "2026-08-24", "share_token": "tok", "target_value": 1905,
         "decompose_mode": "none", "ai_plan": [],
         "daily_calorie_target": TARGET, "gender": "男", "age": 30, "height_cm": 175,
         "weight_kg": 80, "goal_weight": 72, "activity_level": 2},
    ]},
    "/api/v1/challenges/1/today": {"data": {
        "day_number": 2, "date": TODAY, "task_title": "控制每日卡路里摄入",
        "task_description": "把今天吃进肚的食物记录下来。", "task_type": "diet",
        "task_target": TARGET, "task_unit": "千卡", "unit": "千卡", "progress_pct": 0,
        "repeatable": False, "today_total": 0, "today_target": TARGET, "checked_in": False,
        "checkin_data": None, "sub_goals": [], "goal_rule": "fixed", "today_cap": TARGET,
        "remaining": TARGET, "task_tip": "", "task_steps": [], "dynamic_baseline": 0,
        "today_checkins": []}},
    "/api/v1/challenges/1/checkins": {"data": []},
    "/api/v1/challenges/1/mercy": {"data": {"missed_dates": []}},
    "/api/v1/challenges/1/weekly-report": {"data": None},
    "/api/v1/points/summary": {"data": {"total": 120, "week_points": 20}},
    "/api/v1/challenges/1/adaptive/pending": {"data": {"suggestion": None}},
    "/api/v1/challenges/1/guidance": {"data": None},
    "/api/v1/challenges/1/diet/target": {"data": {
        "target_kcal": TARGET, "deficit_kcal": 500, "tdee_kcal": 2405, "bmr_kcal": 1749,
        "current_weight": 80, "goal_weight": 72}},
    "/api/v1/challenges/1/weight/trend": {"data": {
        "records": [
            {"date": "2026-08-24", "weight_kg": 79.8, "avg7": 79.8, "delta": 0.0},
            {"date": TODAY, "weight_kg": 79.5, "avg7": 79.65, "delta": -0.3}],
        "latest": {"date": TODAY, "weight_kg": 79.5, "avg7": 79.65, "delta": -0.3},
        "count": 2}},
}


def route_mock(route, req) -> None:
    url = req.url.split("?")[0]
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
        errs: list[str] = []
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.add_init_script(
            "localStorage.setItem('uc_access_token','mock-token');"
            "localStorage.setItem('uc_refresh_token','mock-r');"
            "localStorage.setItem('cp_user_id','1');localStorage.setItem('cp_nickname','E2E');"
        )
        page.route("**/api/v1/**", route_mock)

        print("== 1. 每日卡路里目标面板 ==")
        page.goto(base + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        if not page.query_selector(".cp-task-card"):
            print("  [debug] errs:", [e[:200] for e in errs][:10])
            print("  [debug] body:", (page.inner_text("body") or "")[:400].replace(chr(10), " | "))
        page.wait_for_selector(".cp-task-card", timeout=45000)
        page.wait_for_selector(".cp-diet-target", timeout=10000)
        target = page.query_selector(".cp-diet-target")
        t = target.inner_text()
        check("显示每日卡路里", "每日卡路里" in t, t)
        check("显示目标摄入", str(TARGET) in t, t)
        check("显示减热量缺口", "减 500 千卡/天" in t, t)

        print("== 2. 饮食记录区(一句话记餐 + AI估算 + 复制昨日) ==")
        page.wait_for_selector(".cp-diet-area", timeout=10000)
        area = page.query_selector(".cp-diet-area")
        at = area.inner_text()
        check("记录今天吃了什么", "记录今天吃了什么" in at, at[:60])
        check("AI 估算按钮", page.query_selector(".cp-diet-est-btn") is not None, "")
        check("复制昨日按钮(无昨日记录时隐藏)", page.query_selector(".cp-diet-copy") is None, "")

        print("== 3. 体重记录与趋势 ==")
        trend_text = page.query_selector(".cp-weight-trend").inner_text()
        check("记录体重区块", page.query_selector(".cp-weight-input") is not None, "")
        check("7日均值标题", "7日均值" in trend_text, trend_text)
        check("今日体重回填79.5", page.query_selector(".cp-weight-input").get_attribute("value") in ("79.5", "79.50"), "")

        print("== 4. 输入描述后点AI估算,出现结果与打卡 ==")
        desc = "早餐鸡蛋牛奶，午餐盒饭，晚餐一碗面"
        page.fill(".cp-diet-input", desc)
        page.route("**/api/v1/challenges/1/diet/estimate", lambda route, req: route.fulfill(
            status=200, content_type="application/json",
            body=json.dumps({"data": {"total_kcal": 1650.0, "confidence": 0.7,
                                      "target_kcal": TARGET, "deficit_kcal": 500,
                                      "assessment": {"status": "under", "label": "摄入偏少", "percent": 86.6},
                                      "items": [{"name": "鸡蛋", "kcal": 120}, {"name": "盒饭", "kcal": 780}],
                                      "min_kcal": 1400, "max_kcal": 1900, "bmr_kcal": 1749, "tdee_kcal": 2405}})))
        page.click(".cp-diet-est-btn")
        page.wait_for_selector(".cp-diet-result", timeout=10000)
        result = page.query_selector(".cp-diet-result")
        rt = result.inner_text()
        check("估算结果展示总计", "1650" in rt, rt[:80])
        check("达标判定展示", "摄入偏少" in rt, rt)
        check("以此打卡按钮", "以此打卡" in rt, "")
        check("重新描述按钮", "重新描述" in rt, "")

        print("== 5. 创建弹窗可打开(overlay渲染) ==")
        page.evaluate("window.cpCreate.open()")
        page.wait_for_timeout(800)
        ov = page.query_selector(".cp-modal-overlay")
        check("cpCreate.open 渲染 overlay", ov is not None, "")
        if ov is None:
            print("  [debug] errs:", [e[:200] for e in errs][:10])

        browser.close()

    httpd.shutdown()
    print("\n===== 汇总 =====")
    print(f"通过 {len(passed)} 项, 失败 {len(failed)} 项")
    for name, d in failed:
        print(f"  FAILED: {name} :: {d}")
    if errs:
        print("\n控制台错误(前8条):")
        for e in errs[:8]:
            print("  -", e[:160])
    else:
        print("\n无控制台错误")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()