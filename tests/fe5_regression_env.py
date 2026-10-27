"""8610 存量回归环境：Lion stub+UC stub 同端口自包含（f2/f3/f4 复活）。

用法：python3 tests/fe5_regression_env.py &  → 8610 就绪后跑 f2/f3/f4，结束时 kill。
"""
import datetime
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, ".")

PORT = 8610
STUB_PORT = 9535
SECRET = "cp-fe5-regression-secret" * 2

os.environ.update(
    UC__JWT_SECRET=SECRET,
    UC__APP_KEY="cp-fe5-reg",
    UC__APP_SECRET="cp-fe5-reg-secret",
    UC__BASE_URL=f"http://127.0.0.1:{STUB_PORT}",
    LION__BASE_URL=f"http://127.0.0.1:{STUB_PORT}",
    NOTIFY_CENTER_URL="http://127.0.0.1:1",
    SERVICE_TOKEN="cp-fe5-reg-service",
    REMINDER_GUARD_OFF="1",
    RATE_LIMIT__REQUESTS_PER_MINUTE="100000",
)
_tmpdb = "/tmp/cp_fe5_regression.db"
if os.path.exists(_tmpdb):
    os.remove(_tmpdb)
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb


class Stub(BaseHTTPRequestHandler):
    def _send(self, body, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/llm/chat"):
            value = json.dumps({"api_key": "stub", "base_url": "http://127.0.0.1:1", "model": "stub"})
            self._send(json.dumps({"code": 200, "data": {"value": value}}).encode())
        else:
            self._send(b'{"code": 404, "message": "Config not found: stub"}')

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        if self.path.rstrip("/").endswith("/api/auth/register"):
            import jwt

            try:
                req = json.loads(raw or b"{}")
            except Exception:
                req = {}
            uid = "reg_" + str(abs(hash(req.get("username", "u"))) % 10_000_000)
            now = int(time.time())
            access = jwt.encode({"sub": uid, "exp": now + 7200}, SECRET, algorithm="HS256")
            refresh = jwt.encode({"sub": uid, "typ": "refresh", "exp": now + 86400}, SECRET, algorithm="HS256")
            self._send(json.dumps({
                "success": True,
                "data": {
                    "access_token": access, "refresh_token": refresh,
                    "user": {"id": uid, "username": req.get("username", ""), "nickname": "回归用户"},
                },
            }).encode())
        elif self.path.rstrip("/").endswith("/api/auth/refresh"):
            self._send(b'{"success": false, "detail": "stub no refresh"}')
        else:
            self._send(b'{"code": 404, "message": "stub"}')

    def log_message(self, *a):
        return None


def main():
    srv = HTTPServer(("127.0.0.1", STUB_PORT), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"stub up on {STUB_PORT}", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        env=dict(os.environ), cwd=".",
        stdout=subprocess.DEVNULL, stderr=open("/tmp/cp_fe5_regression.log", "wb"),
    )
    try:
        for i in range(60):
            time.sleep(0.5)
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1)
                print(f"8610 healthy after {(i + 1) / 2}s", flush=True)
                break
            except Exception:
                if i == 59:
                    print("FAILED to start:", open("/tmp/cp_fe5_regression.log").read()[-800:], flush=True)
                    sys.exit(1)
        print("REGRESSION_ENV_READY", flush=True)
        while proc.poll() is None:
            time.sleep(1)
    finally:
        proc.terminate()
        srv.shutdown()


if __name__ == "__main__":
    main()
