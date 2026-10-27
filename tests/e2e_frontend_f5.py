"""前5 浏览器 E2E：毕业的第一眼——深链承接卡+证书诚实化+弹窗语义+保存双通道。

真服真 API 真数据（仅认证同钥铸造），双种子：
  chA 缺席毕业（最后打卡 14 天前，absence 在场）——承接卡互斥/证书缺席诚实格
  chB 在场毕业（最后打卡 1 天前）——承接卡签名位/证书 pct 保留
证书画布文字经 getContext spy 逐字断言（渲染层真验证）。
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, ".")

PORT = 8616
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "cp-fe5-secret" * 2
OUT = "../out/fe5"
os.makedirs(OUT, exist_ok=True)

os.environ.update(
    UC__JWT_SECRET=SECRET,
    UC__APP_KEY="cp-fe5",
    UC__APP_SECRET="cp-fe5-secret",
    LION__BASE_URL="http://127.0.0.1:9534",
    NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-fe5-service",
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
        ids = {}
        for key, uid, title, recs in (
            ("absent", "fe5a", "戒断·缺席毕业", ((22, 8.0), (14, 6.0))),
            ("present", "fe5b", "戒断·在场毕业", ((22, 8.0), (16, 6.0), (10, 5.0), (4, 4.0), (1, 3.0))),
        ):
            start = shift(22)
            end = (datetime.date.today() + datetime.timedelta(days=38)).strftime("%Y-%m-%d")
            ch = Challenge(
                user_id=uid, title=title, category="quit", duration_days=60,
                start_date=start, end_date=end, task_type="counter", unit="根",
                direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
                target_value=15.0, status="active",
                ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
            )
            s.add(ch)
            await s.commit()
            await s.refresh(ch)
            for days_ago, value in recs:
                d = shift(days_ago)
                dn = day_number_of(start, d)
                await CheckInRepository().create(s, {
                    "challenge_id": ch.id, "user_id": uid, "day_number": dn,
                    "status": "completed",
                    "timestamp": datetime.datetime.strptime(d + " 21:00", "%Y-%m-%d %H:%M"),
                    "date": d, "value": value, "unit": "根",
                    "target_value": float(daily_target(ch, dn)), "goal_type": "soft",
                    "direction": "decrease", "completion_pct": 100.0,
                })
            await s.commit()
            ids[key] = int(ch.id)
        return ids


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

    srv = HTTPServer(("127.0.0.1", 9534), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


CERT_SPY = (
    "window.__fillTextLog = [];"
    "(function(){const orig = HTMLCanvasElement.prototype.getContext;"
    "HTMLCanvasElement.prototype.getContext = function(...a){"
    "const ctx = orig.apply(this, a);"
    "if (ctx && !ctx.__wrapped){ctx.__wrapped = true;"
    "const of = ctx.fillText.bind(ctx);"
    "ctx.fillText = function(...f){window.__fillTextLog.push(String(f[0]));return of(...f)};"
    "} return ctx}})();"
)

SHARE_STUB = (
    "window.__sharePayload = null;"
    "navigator.share = (d) => { window.__sharePayload = JSON.stringify(d && d.files ? {files: d.files.length} : d); return Promise.resolve() };"
    "navigator.canShare = (d) => !!(d && d.files);"
)


def main():
    from playwright.sync_api import sync_playwright

    stub = _lion_stub()
    ids = __import__("asyncio").run(seed())
    ch_a, ch_b = ids["absent"], ids["present"]
    tokens = {"fe5a": mint("fe5a"), "fe5b": mint("fe5b")}
    token = tokens["fe5b"]
    errors: list[str] = []
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=dict(os.environ), cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_fe5_e2e.log", "wb"),
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

            def open_page(path, vw=1440, vh=900, uid="fe5b", stub_share=False):
                pg = browser.new_page(viewport={"width": vw, "height": vh})
                pg.add_init_script(
                    "window.localStorage.setItem('uc_access_token', '" + tokens[uid] + "');"
                    "window.localStorage.setItem('cp_user_id', '" + uid + "');"
                    + CERT_SPY + (";" + SHARE_STUB if stub_share else "")
                )
                pg.on("pageerror", lambda e: errors.append(str(e)))
                pg.goto(BASE + path, wait_until="networkidle")
                pg.wait_for_timeout(1800)
                return pg

            print("== 在场毕业：承接卡签名位 ==")
            pg = open_page(f"/?ch={ch_b}&grad=1")
            gw = pg.locator('[data-testid="grad-welcome"]')
            check("G1 承接卡渲染", gw.count() > 0 and gw.first.is_visible(), f"count={gw.count()}")
            if gw.count():
                txt = gw.first.inner_text()
                check("G1a 阶梯收束主行", "从每天约 12" in txt and "走到 3" in txt, txt[:80])
                check("G1b 记录在案副行", "累计少抽" in txt, txt[:120])
                check("G1c 不会过期信任行", "不会过期" in txt, txt[:160])
            btn = pg.locator('[data-testid="grad-welcome-btn"]')
            check("G2 主钮在场", btn.count() > 0, f"count={btn.count()}")
            pg.screenshot(path=f"{OUT}/g1_grad_welcome_1440.png")
            if btn.count():
                btn.first.click()
                pg.wait_for_timeout(2500)
                modal = pg.locator('[data-testid="share-modal"]')
                check("G2a 证书弹窗打开", modal.count() > 0 and modal.first.is_visible(), f"count={modal.count()}")
                if modal.count():
                    h3 = modal.locator("h3").first.inner_text()
                    check("G2b 弹窗标题=毕业证书", h3 == "毕业证书", h3)
                    hint = modal.locator(".cp-share-hint").inner_text()
                    check("G2c hint 永久保留", "永久保留" in hint, hint)
                log = pg.evaluate("window.__fillTextLog")
                check("G3 在场证书保留减量幅度", any("-" in t and "%" in t for t in log) and any("减量幅度" in t for t in log),
                      str([t for t in log if "%" in t][:3]))
                pg.screenshot(path=f"{OUT}/g2_cert_modal_present_1440.png")

            print("== 保存双通道 ==")
            pg2 = open_page(f"/?ch={ch_b}&grad=1", stub_share=True)
            pg2.locator('[data-testid="grad-welcome-btn"]').first.click()
            pg2.wait_for_timeout(2500)
            save_btn = pg2.locator('[data-testid="share-modal"] .cp-modal-footer .cp-btn-primary')
            check("G9a 保存按钮在场", save_btn.count() > 0, f"count={save_btn.count()}")
            if save_btn.count():
                save_btn.first.click()
                pg2.wait_for_timeout(1200)
                payload = pg2.evaluate("window.__sharePayload")
                check("G9b canShare 命中走 share 面板", bool(payload) and "files" in str(payload), str(payload))
            pg2.close()

            pg3 = open_page(f"/?ch={ch_b}&grad=1")
            pg3.locator('[data-testid="grad-welcome-btn"]').first.click()
            pg3.wait_for_timeout(2500)
            save3 = pg3.locator('[data-testid="share-modal"] .cp-modal-footer .cp-btn-primary')
            if save3.count():
                with pg3.expect_download(timeout=6000) as dl:
                    save3.first.click()
                d = dl.value
                check("G9c 无 canShare 走 download 兜底", d.suggested_filename.endswith(".png"), d.suggested_filename)
            else:
                check("G9c 无 canShare 走 download 兜底", False, "no save btn")
            pg3.close()

            print("== 承接卡动线 ==")
            pg4 = open_page(f"/?ch={ch_b}&grad=1")
            gw4 = pg4.locator('[data-testid="grad-welcome"]')
            check("G4 深链在场", gw4.count() > 0, "")
            dis = pg4.locator(".cp-grad-welcome-dismiss")
            if dis.count():
                dis.first.click()
                pg4.wait_for_timeout(600)
                check("G5 先逛逛收起", pg4.locator('[data-testid="grad-welcome"]').count() == 0, "")
                pg4.reload(wait_until="networkidle")
                pg4.wait_for_timeout(1500)
                check("G5a 当日刷新不复活", pg4.locator('[data-testid="grad-welcome"]').count() == 0, "")
            pg5 = open_page(f"/?ch={ch_b}")
            check("G4a 非深链不渲染", pg5.locator('[data-testid="grad-welcome"]').count() == 0, "")
            pg5.close()

            print("== 缺席毕业：互斥+诚实证书 ==")
            pg6 = open_page(f"/?ch={ch_a}&grad=1", uid="fe5a")
            check("G6 缺席卡在场承接卡互斥",
                  pg6.locator('[data-testid="absence-card"]').count() > 0
                  and pg6.locator('[data-testid="grad-welcome"]').count() == 0, "")
            ab = pg6.locator('[data-testid="absence-grad-btn"]')
            check("G7 缺席卡主钮在场", ab.count() > 0, "")
            pg6.screenshot(path=f"{OUT}/g6_absent_mutual_1440.png")
            if ab.count():
                ab.first.click()
                pg6.wait_for_timeout(2500)
                log = pg6.evaluate("window.__fillTextLog")
                check("G7a 缺席证书无减量幅度格", not any("减量幅度" in t for t in log) and not any("%" in t for t in log),
                      str([t for t in log if "%" in t or "减量" in t][:3]))
                check("G7b 缺席证书记录天数格", any("记录天数" in t for t in log), str([t for t in log if "天数" in t][:3]))
                cp = pg6.locator('[data-testid="share-modal"] .cp-modal-footer button', has_text="复制文案")
                if cp.count():
                    pg6.evaluate(
                        "window.__copyTextLog=[];const oc=window.NexusUtils.copyText.bind(window.NexusUtils);"
                        "window.NexusUtils.copyText=(t,o)=>{window.__copyTextLog.push(String(t));return oc(t,o)}"
                    )
                    cp.first.click()
                    pg6.wait_for_timeout(600)
                    clip = pg6.evaluate("(window.__copyTextLog || []).join('||')")
                    check("G7c 复制文案缺席无百分比", "%" not in clip and "少抽" in clip, clip[:90])
                pg6.screenshot(path=f"{OUT}/g7_cert_absent_1440.png")
            pg6.close()

            print("== 375 + 暗色 ==")
            pgm = open_page(f"/?ch={ch_b}&grad=1", vw=375, vh=812)
            check("G11a 375 承接卡渲染", pgm.locator('[data-testid="grad-welcome"]').count() > 0, "")
            ov = pgm.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("G11b 375 零横向溢出", ov == 0, f"ov={ov}")
            modal_m = pgm.locator('[data-testid="share-modal"]')
            if not modal_m.count():
                pgm.locator('[data-testid="grad-welcome-btn"]').first.click()
                pgm.wait_for_timeout(2500)
            lp = pgm.locator(".cp-share-longpress")
            check("G10 375 长按提示可见", lp.count() > 0 and lp.first.is_visible(), f"count={lp.count()}")
            pgm.screenshot(path=f"{OUT}/g11_375_welcome.png")
            pgm.close()
            pgd = open_page(f"/?ch={ch_b}&grad=1", vw=375, vh=812)
            pgd.add_init_script("window.localStorage.setItem('nx-theme','dark');")
            pgd.close()
            ctx_d = browser.new_context(viewport={"width": 375, "height": 812})
            ctx_d.add_init_script(
                "window.localStorage.setItem('uc_access_token', '" + token + "');"
                "window.localStorage.setItem('cp_user_id', 'fe5b');"
                "window.localStorage.setItem('nx-theme', 'dark');"
            )
            pd = ctx_d.new_page()
            pd.on("pageerror", lambda e: errors.append("dark:" + str(e)))
            pd.goto(BASE + f"/?ch={ch_b}&grad=1", wait_until="networkidle")
            pd.wait_for_timeout(1800)
            bg = pd.evaluate(
                "(()=>{const el=document.querySelector('[data-testid=grad-welcome]');"
                "return el?getComputedStyle(el).backgroundImage.slice(0,60):''})()"
            )
            theme = pd.evaluate("document.documentElement.getAttribute('data-theme')")
            check("G12 暗色主题生效+承接卡在场", theme == "dark" and pd.locator('[data-testid="grad-welcome"]').count() > 0,
                  f"theme={theme}")
            pd.screenshot(path=f"{OUT}/g12_375_dark.png")
            ctx_d.close()

            check("G13 零 pageerror", len(errors) == 0, str(errors[:3]))
            browser.close()
    finally:
        proc.terminate()
        stub.shutdown()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()

    print(f"\n=== e2e_frontend_f5: {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
