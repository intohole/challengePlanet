"""前5 基线取证：毕业承接面三端双主题+痛点探针（复用 r23_browser 配方）。

取证面：grad 深链落地形态/证书弹窗语义/证书 pct 口径/缺席卡按钮堆叠/375 弹窗。
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")

PORT = 8614
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "cp-fe5-baseline-secret" * 2
OUT = "../out/fe5_baseline"
os.makedirs(OUT, exist_ok=True)

os.environ.update(
    UC__JWT_SECRET=SECRET,
    UC__APP_KEY="cp-fe5-base",
    UC__APP_SECRET="cp-fe5-base-secret",
    LION__BASE_URL="http://127.0.0.1:9530",
    NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-fe5-base-service",
    REMINDER_GUARD_OFF="1",
)
_tmpdb = tempfile.mkstemp(suffix=".db")[1]
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb

findings: list[str] = []


def note(msg):
    findings.append(msg)
    print("  :: " + msg)


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
        start = shift(22)
        end = (datetime.date.today() + datetime.timedelta(days=38)).strftime("%Y-%m-%d")
        ch = Challenge(
            user_id="fe5base", title="戒断取证挑战", category="quit", duration_days=60,
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
                "challenge_id": ch.id, "user_id": "fe5base", "day_number": dn,
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

    srv = HTTPServer(("127.0.0.1", 9530), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def main():
    from playwright.sync_api import sync_playwright

    stub = _lion_stub()
    cid = __import__("asyncio").run(seed())
    token = mint("fe5base")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=dict(os.environ), cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_fe5_baseline.log", "wb"),
    )
    try:
        for _ in range(40):
            time.sleep(0.5)
            try:
                import urllib.request

                urllib.request.urlopen(BASE + "/health", timeout=1)
                break
            except Exception:
                pass

        with sync_playwright() as p:
            browser = p.chromium.launch()

            def new_page(vw, vh, dark=False):
                pg = browser.new_page(viewport={"width": vw, "height": vh})
                pg.add_init_script(
                    "window.localStorage.setItem('uc_access_token', '" + token + "');"
                    "window.localStorage.setItem('cp_user_id', 'fe5base');"
                    + ("document.documentElement.setAttribute('data-theme','dark');" if dark else "")
                )
                return pg

            def api_today(pg):
                return pg.evaluate(
                    "fetch(window.location.origin + window.PATH_PREFIX + '/api/v1/challenges/%s/today',"
                    "{headers:{Authorization:'Bearer '+localStorage.getItem('uc_access_token')}})"
                    ".then(r=>r.json())" % cid
                )

            page = new_page(1440, 900)
            errs = []
            page.on("pageerror", lambda e: errs.append(str(e)))

            print("== A. grad 深链落地形态 ==")
            page.goto(BASE + f"/?ch={cid}&grad=1", wait_until="networkidle")
            page.wait_for_timeout(1800)
            cert_on_land = page.locator(".cp-modal:visible").count()
            note(f"A1 深链落地可见弹窗数={cert_on_land}（预期 0=承接断在 toast）")
            body_txt = page.locator("#view-root").inner_text()
            note(f"A2 落地页含'毕业'字样={'毕业' in body_txt}")
            toasts = page.locator(".nxs-toast, .nux-toast, [class*=toast]").count()
            note(f"A3 toast 元素数={toasts}（6s 后即消失）")
            page.screenshot(path=f"{OUT}/a1_deeplink_landing_1440.png")

            print("== B. today API journey 口径 ==")
            t = api_today(page)
            j = ((t.get("data") or t).get("journey") or {})
            note(f"B1 journey.reduction_pct={j.get('reduction_pct')} recent_avg={j.get('recent_avg')} "
                 f"baseline={j.get('baseline')} avoided={j.get('cigarettes_avoided')}")
            note(f"B1' 缺席 14 天的证书将印 -{j.get('reduction_pct')}%（来自缺勤前均值 {j.get('recent_avg')}）")

            print("== C. 缺席卡形态 ==")
            card = page.locator('[data-testid="absence-card"]')
            note(f"C1 缺席卡 count={card.count()}")
            if card.count():
                btns = card.first.locator("button").count()
                note(f"C2 缺席卡按钮数={btns}")
                note("C3 缺席卡文本=" + card.first.inner_text().replace("\n", " | ")[:150])
            page.screenshot(path=f"{OUT}/a2_absence_card_1440.png")

            print("== D. 证书弹窗语义 ==")
            page.locator('[data-testid="absence-grad-btn"]').first.click()
            page.wait_for_timeout(300)
            loading = page.locator(".cp-share-loading").inner_text() if page.locator(".cp-share-loading").count() else "(已出图)"
            note(f"D1 loading 文案={loading}")
            page.wait_for_timeout(2500)
            title = page.locator(".cp-modal:visible .cp-modal-header h3").first.inner_text()
            note(f"D2 弹窗标题={title}")
            tabs = page.locator(".cp-scope-tabs button").all_inner_texts()
            note(f"D3 tabs={tabs}")
            hint = page.locator(".cp-share-hint").inner_text() if page.locator(".cp-share-hint").count() else ""
            note(f"D4 hint={hint}")
            footer_btns = page.locator(".cp-modal:visible .cp-modal-footer button").all_inner_texts()
            note(f"D5 底部按钮={footer_btns}")
            note(f"D6 navigator.share files 支持={page.evaluate('!!(navigator.canShare && navigator.canShare({files:[new File([\"\"],\"a.png\",{type:\"image/png\"})]}))')}")
            page.screenshot(path=f"{OUT}/a3_cert_modal_1440.png")
            page.close()

            print("== E. 三端双主题 ==")
            for w, h, tag in ((1400, 900, "1400"), (1024, 768, "1024"), (375, 812, "375")):
                for dark in (False, True):
                    pg = new_page(w, h, dark)
                    pg.on("pageerror", lambda e, _p=pg: errs.append(str(e)))
                    pg.goto(BASE + f"/?ch={cid}&grad=1", wait_until="networkidle")
                    pg.wait_for_timeout(1800)
                    pg.screenshot(path=f"{OUT}/v_{tag}_{'dark' if dark else 'light'}.png")
                    if tag == "375":
                        ov = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                        note(f"E375 横向溢出={ov}px")
                        pg.locator('[data-testid="absence-grad-btn"]').first.click()
                        pg.wait_for_timeout(2500)
                        img = pg.locator(".cp-share-img").first.bounding_box()
                        note(f"E375 证书图 box={img and (round(img['width']),round(img['height']))}")
                        pg.screenshot(path=f"{OUT}/v_375_cert_modal.png")
                    pg.close()

            print("== F. pageerror ==")
            note(f"F1 pageerror={errs[:3] if errs else '无'}")
            browser.close()
    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"\n=== 基线取证完成，{len(findings)} 条 ===")


if __name__ == "__main__":
    main()
