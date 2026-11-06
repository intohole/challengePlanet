"""S110 子路径可达守底——平台共享资产引用三口径契约(撤修复必红)。星轨挑战判例仓。

仿真生产拓扑(nginx location ^~ /<prefix>/ 剥前缀 + sub_filter 根绝对改写 + FastAPI 挂载面):
  /static/* → STATIC_DIR;  / → index.html;  /login → login.html
断言: 每个入口页的平台共享资产引用(nux-icons/icon.svg/favicon)按浏览器语义解析后
HTTP GET 全 200。引用回退相对形态(裸 nux-icons.css / css/...) → 落未挂载路径 404 → 本测试红。
"""
from __future__ import annotations

import re
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
PREFIX = "/app"
ASSET_RE = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
PLATFORM_RE = re.compile(r"nux-icons|favicon|icon\.svg", re.IGNORECASE)
EXTERNAL_RE = re.compile(r"^(https?:)?//", re.IGNORECASE)


class _Sim(BaseHTTPRequestHandler):
    def log_message(self, *a):  # noqa: ANN002,ARG002
        return

    def do_GET(self):  # noqa: N802
        path = unquote(self.path.split("?")[0])
        inner = path[len(PREFIX):] if path.startswith(PREFIX) else path
        f = None
        if inner.startswith("/static/"):
            f = STATIC_DIR / inner[len("/static/"):]
        elif inner == "/":
            f = STATIC_DIR / "index.html"
        elif inner == "/login":
            f = STATIC_DIR / "login.html"
        if f is not None and f.is_file():
            body = f.read_bytes()
            self.send_response(200)
        else:
            body = b""
            self.send_response(404)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _fetch_pages_and_refs(base: str) -> list[tuple[str, str, int]]:
    rows: list[tuple[str, str, int]] = []
    for entry, _unused in (("/", "index"), ("/login", "login")):
        page_url = f"{base}{PREFIX}{entry}"
        try:
            html = urllib.request.urlopen(page_url, timeout=5).read().decode("utf-8", "replace")
        except Exception:
            continue
        for ref in ASSET_RE.findall(html):
            if not PLATFORM_RE.search(ref) or EXTERNAL_RE.match(ref):
                continue
            clean = ref.split("#")[0].split("?")[0]
            eff = f"{base}{PREFIX}{clean}" if clean.startswith("/") else f"{page_url.rsplit('/', 1)[0]}/{clean}"
            try:
                status = urllib.request.urlopen(eff, timeout=5).status
            except urllib.error.HTTPError as e:
                status = e.code
            rows.append((entry, ref, status))
    return rows


def test_platform_asset_refs_reachable_under_subpath():
    port = 18731
    srv = ThreadingHTTPServer(("127.0.0.1", port), _Sim)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        rows = _fetch_pages_and_refs(f"http://127.0.0.1:{port}")
    finally:
        srv.shutdown()
        srv.server_close()
    assert rows, "未提取到平台资产引用(探针失效)"
    bad = [(p, r, s) for p, r, s in rows if s != 200]
    assert not bad, f"平台共享资产子路径 404(引用形态×挂载面失配): {bad}"
