"""前5 三端双主题截图矩阵：承接卡+证书弹窗（1400/1024/375 × 亮/暗）。"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")

PORT = 8617
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "cp-fe5-shots-secret" * 2
OUT = "../out/fe5_shots"
os.makedirs(OUT, exist_ok=True)

os.environ.update(
    UC__JWT_SECRET=SECRET, UC__APP_KEY="cp-fe5-shots", UC__APP_SECRET="cp-fe5-shots-secret",
    LION__BASE_URL="http://127.0.0.1:9536", NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-fe5-shots-service", REMINDER_GUARD_OFF="1",
)
_tmpdb = "/tmp/cp_fe5_shots.db"
if os.path.exists(_tmpdb):
    os.remove(_tmpdb)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb


def shift(d_ago):
    return (datetime.date.today() - datetime.timedelta(days=d_ago)).strftime("%Y-%m-%d")


async def seed():
    from app.db.database import init_db, run_migrations, async_session
    from app.models.challenge import Challenge
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.goal_rule_service import daily_target
    from app.services.streak_service import day_number_of

    await init_db()
    await run_migrations()
    async with async_session() as s:
        start = shift(22)
        end = (datetime.date.today() + datetime.timedelta(days=38)).strftime("%Y-%m-%d")
        ch = Challenge(user_id="fe5shots", title="戒断·毕业之旅", category="quit", duration_days=60,
            start_date=start, end_date=end, task_type="counter", unit="根", direction="decrease",
            goal_type="soft", goal_rule="ladder", goal_mode="ceiling", target_value=15.0, status="active",
            ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0)
        s.add(ch)
        await s.commit()
        await s.refresh(ch)
        for d_ago, v in ((22, 8.0), (16, 6.0), (10, 5.0), (4, 4.0), (1, 3.0)):
            d = shift(d_ago)
            dn = day_number_of(start, d)
            await CheckInRepository().create(s, {"challenge_id": ch.id, "user_id": "fe5shots", "day_number": dn,
                "status": "completed", "timestamp": datetime.datetime.strptime(d + " 21:00", "%Y-%m-%d %H:%M"),
                "date": d, "value": v, "unit": "根", "target_value": float(daily_target(ch, dn)),
                "goal_type": "soft", "direction": "decrease", "completion_pct": 100.0})
        await s.commit()
        return int(ch.id)


def _lion_stub():
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            import json as _json

            if self.path.rstrip("/").endswith("/llm/chat"):
                value = _json.dumps({"api_key": "k", "base_url": "http://127.0.0.1:1", "model": "m"})
                body = _json.dumps({"code": 200, "data": {"value": value}}).encode()
            else:
                body = b'{"code": 404, "message": "Config not found: stub"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            return None

    srv = HTTPServer(("127.0.0.1", 9536), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    import jwt
    from playwright.sync_api import sync_playwright

    stub = _lion_stub()
    cid = __import__("asyncio").run(seed())
    token = jwt.encode({"sub": "fe5shots", "exp": int(time.time()) + 7200}, SECRET, algorithm="HS256")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=dict(os.environ), cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_fe5_shots.log", "wb"),
    )
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(BASE + "/health", timeout=1)
                break
            except Exception:
                pass

        with sync_playwright() as p:
            browser = p.chromium.launch()
            for w, h, tag in ((1400, 900, "1400"), (1024, 768, "1024"), (375, 812, "375")):
                for theme in ("light", "dark"):
                    ctx = browser.new_context(viewport={"width": w, "height": h})
                    ctx.add_init_script(
                        "window.localStorage.setItem('uc_access_token', '" + token + "');"
                        "window.localStorage.setItem('cp_user_id', 'fe5shots');"
                        + (f"window.localStorage.setItem('nx-theme','{theme}');" if theme == "dark" else "")
                    )
                    pg = ctx.new_page()
                    pg.goto(BASE + f"/?ch={cid}&grad=1", wait_until="networkidle")
                    pg.wait_for_timeout(1800)
                    pg.screenshot(path=f"{OUT}/welcome_{tag}_{theme}.png")
                    btn = pg.locator('[data-testid="grad-welcome-btn"]')
                    if btn.count():
                        btn.first.click()
                        pg.wait_for_timeout(2600)
                        pg.screenshot(path=f"{OUT}/cert_{tag}_{theme}.png")
                    pg.close()
                    ctx.close()
            browser.close()
        print("shots done ->", OUT)
    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    main()
