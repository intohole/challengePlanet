"""r23 浏览器 E2E：缺席中的毕业——cap 挑战缺席卡 graduated 变体+点击出毕业证书。

真服真 API 真数据（仅认证同钥铸造），造「阶梯已毕业+缺席 10 天」的戒断挑战，
断言缺席卡变为「毕业证书在等你」变体与点击后的证书分享弹窗。
注意：cap 挑战的回归承接面是缺席卡（valid_dates 静默守住语义，回归 hero 只属
learn 挑战），毕业 CTA 必须落在缺席卡——这正是 r22 回归页设计覆盖面的补全。
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")

PORT = 8613
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "cp-r23-browser-secret" * 2

os.environ.update(
    UC__JWT_SECRET=SECRET,
    UC__APP_KEY="cp-r23-browser",
    UC__APP_SECRET="cp-r23-browser-secret",
    LION__BASE_URL="http://127.0.0.1:9529",
    NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-r23-browser-service",
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
        # 间隔 2、12→3：goal_day=19；start=22 天前 → 前天已毕业；最后打卡 14 天前=缺席中
        start = shift(22)
        end = (datetime.date.today() + datetime.timedelta(days=38)).strftime("%Y-%m-%d")
        ch = Challenge(
            user_id="r23br", title="戒断 Browser 验证", category="quit", duration_days=60,
            start_date=start, end_date=end, task_type="counter", unit="根",
            direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
            target_value=15.0, status="active",
            ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        )
        s.add(ch)
        await s.commit()
        await s.refresh(ch)
        for days_ago, value in ((22, 8.0), (14, 6.0)):
            d = shift(days_ago)
            dn = day_number_of(start, d)
            await CheckInRepository().create(s, {
                "challenge_id": ch.id, "user_id": "r23br", "day_number": dn,
                "status": "completed",
                "timestamp": datetime.datetime.strptime(d + " 21:00", "%Y-%m-%d %H:%M"),
                "date": d, "value": value, "unit": "根",
                "target_value": float(daily_target(ch, dn)), "goal_type": "soft",
                "direction": "decrease", "completion_pct": 100.0,
            })
        await s.commit()
        return int(ch.id)


def _lion_stub():
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

    srv = HTTPServer(("127.0.0.1", 9529), H)
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
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_r23_browser_e2e.log", "wb"),
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

        token = mint("r23br")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.add_init_script(
                "window.localStorage.setItem('uc_access_token', '" + token + "');"
                "window.localStorage.setItem('cp_user_id', 'r23br');"
            )
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/", wait_until="networkidle")
            page.wait_for_timeout(1500)
            card = page.locator('[data-testid="absence-card"]')
            visible = card.count() > 0 and card.first.is_visible()
            check("B1 缺席卡渲染", visible, f"count={card.count()}")
            if visible:
                text = card.first.inner_text()
                check("B2 graduated 变体标题", "毕业证书在等你" in text, text[:60])
                check("B3 已少抽数字保留", "已少抽" in text, text[:120])
                check("B4 不再写当前上限口吻", "今天上限" not in text, text[:120])
            grad_btn = page.locator('[data-testid="absence-grad-btn"]')
            has_btn = grad_btn.count() > 0 and grad_btn.first.is_visible()
            check("B5 毕业证书 CTA 上桌", has_btn, f"count={grad_btn.count()}")
            page.screenshot(path="../out/r23_absence_grad.png", full_page=False)
            if has_btn:
                grad_btn.first.click()
                page.wait_for_timeout(2500)
                cert_img = page.locator("img[src*='data:image'], .cp-share-modal canvas, .cp-share-body canvas")
                check("B6 点击 CTA 证书出图", cert_img.count() > 0, f"img={cert_img.count()}")
                save_btn = page.locator(".cp-modal-footer .cp-btn-primary")
                if save_btn.count() > 0:
                    h = save_btn.first.bounding_box()
                    check("B8 保存图片按钮不换行", bool(h) and h["height"] < 60, f"h={h and h['height']}")
                page.screenshot(path="../out/r23_grad_cert_modal.png", full_page=False)
            else:
                check("B6 点击 CTA 证书出图", False, "no btn")
            check("B7 零 JS 异常", len(errors) == 0, str(errors[:2]))

            page2 = browser.new_page(viewport={"width": 390, "height": 844})
            page2.add_init_script(
                "window.localStorage.setItem('uc_access_token', '" + token + "');"
                "window.localStorage.setItem('cp_user_id', 'r23br');"
                "document.documentElement.setAttribute('data-theme','dark');"
            )
            page2.on("pageerror", lambda e: errors.append("dark:" + str(e)))
            page2.goto(BASE + "/", wait_until="networkidle")
            page2.wait_for_timeout(1200)
            card2 = page2.locator('[data-testid="absence-card"]')
            check("B9 深色主题缺席卡照常渲染", card2.count() > 0 and card2.first.is_visible(), f"count={card2.count()}")
            page2.screenshot(path="../out/r23_absence_grad_dark.png", full_page=False)
            page2.close()
            browser.close()
    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"\n=== e2e_r23_browser: {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
