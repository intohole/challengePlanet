"""r22 浏览器 E2E：回归页 hero 真渲染（真服真 API 真数据，仅认证用同钥铸造）。

起真 uvicorn（临时库），repo 造「缺席 3 天后回来」数据，浏览器注入 token 走真实
首页动线，断言回归页 hero 的文案、最小动作与回赠进度条。
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")

PORT = 8611
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "cp-r22-browser-secret" * 2

os.environ.update(
    UC__JWT_SECRET=SECRET,
    UC__APP_KEY="cp-r22-browser",
    UC__APP_SECRET="cp-r22-browser-secret",
    LION__BASE_URL="http://127.0.0.1:9528",
    NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-r22-browser-service",
    REMINDER_GUARD_OFF="1",
)
_tmpdb = tempfile.mkstemp(suffix=".db")[1]
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def shift(days_ago):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def mint(uid: str) -> str:
    import jwt

    return jwt.encode({"sub": uid, "exp": int(time.time()) + 7200}, SECRET, algorithm="HS256")


async def seed():
    from app.db.database import init_db, run_migrations, async_session
    from app.models.challenge import Challenge
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.goal_rule_service import daily_target
    from app.services.streak_service import day_number_of

    await init_db()
    await run_migrations()
    async with async_session() as s:
        start = shift(8)
        end = (datetime.date.today() + datetime.timedelta(days=52)).strftime("%Y-%m-%d")
        ch = Challenge(
            user_id="r22br", title=" Browser 回归验证", category="learn", duration_days=60,
            start_date=start, end_date=end, task_type="counter", unit="个",
            direction="increase", goal_type="hard", goal_rule="fixed", goal_mode="floor",
            target_value=20.0, status="active",
        )
        s.add(ch)
        await s.commit()
        await s.refresh(ch)
        dn = day_number_of(start, shift(4))
        await CheckInRepository().create(s, {
            "challenge_id": ch.id, "user_id": "r22br", "day_number": dn,
            "status": "completed",
            "timestamp": datetime.datetime.strptime(shift(4) + " 21:00", "%Y-%m-%d %H:%M"),
            "date": shift(4), "value": 5.0, "unit": "个",
            "target_value": float(daily_target(ch, dn)), "goal_type": "hard",
            "direction": "increase", "completion_pct": 100.0,
        })
        await s.commit()
        return int(ch.id)


def _lion_stub():
    """Lion 桩：所有配置回「Config not found」（nexus.lion 的容错通道，非静默降级）。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            import json as _json

            if self.path.rstrip("/").endswith("/llm/chat"):
                value = _json.dumps({
                    "api_key": "stub-key", "base_url": "http://127.0.0.1:1",
                    "model": "stub-model",
                })
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

    srv = HTTPServer(("127.0.0.1", 9528), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    stub = _lion_stub()
    cid = __import__("asyncio").run(seed())
    env = dict(os.environ)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=env, cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_browser_e2e.log", "wb"),
    )
    try:
        ready = False
        for _ in range(40):
            time.sleep(0.5)
            try:
                import urllib.request

                with urllib.request.urlopen(BASE + "/health", timeout=2) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                continue
        check("B0 服务起+health ok", ready)

        from playwright.sync_api import sync_playwright

        token = mint("r22br")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.add_init_script(
                "window.localStorage.setItem('uc_access_token', '" + token + "');"
                "window.localStorage.setItem('cp_user_id', 'r22br');"
            )
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(1500)
            hero = page.locator('[data-testid="return-hero"]')
            visible = hero.count() > 0 and hero.first.is_visible()
            check("B1 回归页 hero 渲染", visible, f"count={hero.count()}")
            if visible:
                text = hero.first.inner_text()
                check("B2 欢迎回来+回来第 1 天", "欢迎回来" in text and "第 1 天" in text, text[:80])
                check("B3 走过的天都算数+离开 3 天", "3" in text and "都算数" in text, text[:120])
                check("B4 最小动作 4 个", "4 个" in text and "1/5" in text, text[:160])
                check("B5 回赠进度 1/3", "1/3" in text and "免费补签卡" in text, text[:200])
            check("B6 零 JS 异常", len(errors) == 0, str(errors[:2]))
            page.screenshot(path="../out/r22_return_hero.png", full_page=False)
            browser.close()
    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"\n=== e2e_r22_browser: {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
