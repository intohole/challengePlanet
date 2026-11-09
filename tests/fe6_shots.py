#!/usr/bin/env python3
"""fe6 三端双主题截图矩阵: resting 卡+确认弹窗+复活开局条（1400/1024/375 × 亮/暗）。

自起自收: 独立端口 8618+独立库+Lion stub 9538。语义等待（networkidle 在 v2.83.0 CDN 时代不可靠）。
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, ".")

PORT = 8618
BASE = f"http://127.0.0.1:{PORT}"
STUB_PORT = 9538
SECRET = "cp-fe6-shots-secret" * 2
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out", "fe6_shots")
os.makedirs(OUT, exist_ok=True)

os.environ.update(
    UC__JWT_SECRET=SECRET, UC__APP_KEY="cp-fe6-shots", UC__APP_SECRET="cp-fe6-shots-secret",
    UC__BASE_URL=f"http://127.0.0.1:{STUB_PORT}",
    LION__BASE_URL=f"http://127.0.0.1:{STUB_PORT}", NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-fe6-shots-service", REMINDER_GUARD_OFF="1",
    RATE_LIMIT__REQUESTS_PER_MINUTE="100000",
)
_tmpdb = "/tmp/cp_fe6_shots.db"
if os.path.exists(_tmpdb):
    os.remove(_tmpdb)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb

UID = "fe6shots"


def shift(d_ago):
    return (datetime.date.today() - datetime.timedelta(days=d_ago)).strftime("%Y-%m-%d")


async def seed() -> list:
    from app.db.database import init_db, run_migrations, async_session
    from app.models.challenge import Challenge
    from app.models.checkin import CheckIn

    await init_db()
    await run_migrations()
    async with async_session() as s:
        rest_ids = []
        for k in range(6):
            ch = Challenge(user_id=UID, title="减量戒烟：从 12 根到 3 根", category="quit", duration_days=66,
                           start_date="2026-09-09", end_date="2026-11-13", task_type="counter", unit="根",
                           direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
                           target_value=15.0, status="resting", ladder_start=12.0, ladder_goal=3.0,
                           ladder_interval=2, ladder_step=1.0, icon="🚭")
            s.add(ch)
            await s.flush()
            rest_ids.append(int(ch.id))
            for i in range(21):
                d = shift(30 - i)
                s.add(CheckIn(challenge_id=ch.id, user_id=UID, day_number=i + 1, status="kept",
                              timestamp=datetime.datetime.strptime(d + " 21:00", "%Y-%m-%d %H:%M"),
                              date=d, value=1.0, unit="根", target_value=float(12 - i // 2),
                              goal_type="soft", direction="decrease", completion_pct=100.0))
        await s.commit()
        return rest_ids


def _lion_stub():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.rstrip("/").endswith("/llm/chat"):
                value = json.dumps({"api_key": "k", "base_url": "http://127.0.0.1:1", "model": "m"})
                body = json.dumps({"code": 200, "data": {"value": value}}).encode()
            else:
                body = b'{"code": 404, "message": "Config not found: stub"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            return None

    srv = HTTPServer(("127.0.0.1", STUB_PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    import jwt
    from playwright.sync_api import sync_playwright

    stub = _lion_stub()
    rest_ids = asyncio.run(seed())
    token = jwt.encode({"sub": UID, "exp": int(time.time()) + 7200}, SECRET, algorithm="HS256")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=dict(os.environ), cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_fe6_shots.log", "wb"),
    )
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(BASE + "/health", timeout=1)
                break
            except Exception:
                pass

        def boot(pg):
            pg.wait_for_function(
                "window.appState && window.appState.booted && window.appState.challenges.length > 0",
                timeout=30000,
            )
            pg.wait_for_timeout(1800)

        with sync_playwright() as p:
            browser = p.chromium.launch()
            scenes = [(1400, 900, "1400", "light"), (1400, 900, "1400", "dark"),
                      (1024, 768, "1024", "light"), (1024, 768, "1024", "dark"),
                      (375, 812, "375", "light"), (375, 812, "375", "dark")]
            for w, h, tag, theme in scenes:
                cur_id = rest_ids.pop(0)
                ctx = browser.new_context(viewport={"width": w, "height": h})
                ctx.add_init_script(
                    "window.localStorage.setItem('uc_access_token', '" + token + "');"
                    "window.localStorage.setItem('cp_user_id', '" + UID + "');"
                    "window.localStorage.setItem('cp_nickname', '体验轮');"
                    + (f"window.localStorage.setItem('nx-theme','{theme}');" if theme == "dark" else "")
                )
                pg = ctx.new_page()
                # 1) resting 第一眼（全 resting 回流形态；每场景一个独立 resting 挑战，复活不跨场景泄漏）
                pg.goto(BASE + "/", wait_until="domcontentloaded")
                boot(pg)
                if pg.locator('[data-testid="resting-card"]').count() == 0 or not pg.evaluate(
                    "() => window.appState.current && window.appState.current.status === 'resting' && window.appState.current.id === " + str(cur_id)
                ):
                    pg.evaluate(f"window.cpSelectChallenge({cur_id})")
                pg.wait_for_timeout(1200)
                pg.wait_for_selector('[data-testid="resting-card"]', timeout=15000)
                pg.screenshot(path=f"{OUT}/resting_{tag}_{theme}.png")
                # 2) 确认弹窗（375/1400 拍, 1024 跳过省时）
                if tag in ("1400", "375"):
                    pg.click('[data-testid="revive-btn"]')
                    pg.wait_for_timeout(800)
                    pg.screenshot(path=f"{OUT}/confirm_{tag}_{theme}.png")
                    pg.evaluate("() => { const b = Array.from(document.querySelectorAll('button')).find(x => x.textContent.trim() === '取消'); if (b) b.click() }")
                    pg.wait_for_timeout(500)
                # 3) 复活后开局条
                pg.click('[data-testid="revive-btn"]')
                pg.wait_for_timeout(800)
                pg.evaluate("() => { const b = Array.from(document.querySelectorAll('button')).find(x => x.textContent.trim() === '确定'); if (b) b.click() }")
                for _ in range(45):
                    pg.wait_for_timeout(1000)
                    ready = pg.evaluate(
                        "() => window.cpViews.home.data.today && Object.keys(window.cpViews.home.data.today).length > 10 && !window.cpViews.home.data.loading"
                    )
                    if ready:
                        break
                pg.wait_for_timeout(800)
                pg.screenshot(path=f"{OUT}/revived_{tag}_{theme}.png")
                pg.screenshot(path=f"{OUT}/revived_{tag}_{theme}_full.png", full_page=True)
                ctx.close()
            browser.close()
        print("shots done ->", OUT)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
