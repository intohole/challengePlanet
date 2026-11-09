"""fe_env2 —— 行为级 E2E 环境账 canon 单源（S120，handoff/94）.

五原语（逐判例对表 optimize_frontend_history/lessons.md，不新造语义）：
  B CDN资产  ensure_cdn/apply_cdn   #12/#19/#29 CDN 随机波动→本地映射（truemirror fe_env 参数化平移）
  A 鉴权     trio_env/uc_token/ensure_authstate   #29 三件套一起给漏一无效 / verseCraft fe5 HS256 / #30 守卫 / #9 存在性先探
  C 进程     serve_app              resumeAI 前7 Popen 自起自收 / verseCraft fe5 19xxx 端口 / verseCraft fe5 stub 黑洞
  D 等待     goto_app/wait_state    #13 语义等待（固定睡≥600ms=竞态彩票）/ #30 等待窗=最后一块异步数据
  E 数据     iso_db                 #12 残片 rmtree / fkg 前6 串户 sweep / #42 状态耦合复原
  F 服务发现 isolate_discovery     S124 discovery 快照劫持（~/.cache 快照恒压 env→SDK 打生产）；
                                   只隔离 DISCOVERY_CACHE_PATH 不动 UC/MINIDEPLOY 键（fe9 隧道形态），
                                   必须在 import nexus/app 前进入，或先调 nexus.discovery.reset_registry()

舰队纪律：本文件是母版（scripts/canon/fe_env2.py），平移=逐字节复制进各仓 tests/fe_env2.py，
不建跨仓 import 不建 pip 包（S119 判例同款）；漂移由 scripts/s120_e2e_env_audit.py R3 对表。
用法示例见 scripts/test_fe_env_canon.py。
"""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import signal
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

CDN_PREFIX = "https://songguokr.com/nexus-ui/"
TRIO_KEYS = ("DISCOVERY_CACHE_PATH", "MINIDEPLOY_BASE_URL", "UC__BASE_URL")


def ensure_cdn(index_html: Path, cache_dir: Path | None = None, prefix: str = CDN_PREFIX) -> Path:
    cache = cache_dir or Path(tempfile.gettempdir()) / "fe_env2_cdn"
    cache.mkdir(parents=True, exist_ok=True)
    urls = sorted(set(re.findall(
        re.escape(prefix) + r'[^"\'\s]+',
        Path(index_html).read_text(encoding="utf-8"))))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for url in urls:
        rel = url.split(prefix)[-1].split("?")[0]
        f = cache / rel
        if f.exists() and f.stat().st_size:
            continue
        f.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(3):
            try:
                f.write_bytes(urllib.request.urlopen(url, timeout=20, context=ctx).read())
                break
            except Exception:
                time.sleep(1)
    return cache


def _ctype_of(rel: str) -> str:
    return {"css": "text/css", "js": "application/javascript"}.get(
        rel.rsplit(".", 1)[-1], "application/octet-stream")


def _fetch_missing(url: str, f: Path) -> bool:
    """cache-on-miss：动态加载的组件脚本不在 index.html 引用集里（moutain nux-*.js 判例），
    首次请求现场抓取入缓存，抓不到才放弃。"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    for _ in range(2):
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(urllib.request.urlopen(url, timeout=15, context=ctx).read())
            return True
        except Exception:
            time.sleep(0.5)
    return False


def apply_cdn(context, cache_dir: Path, prefix: str = CDN_PREFIX) -> None:
    def fulfill(route):
        rel = route.request.url.split(prefix)[-1].split("?")[0]
        f = Path(cache_dir) / rel
        if not (f.exists() and f.stat().st_size):
            if not _fetch_missing(route.request.url, f):
                route.abort()
                return
        route.fulfill(path=str(f), content_type=_ctype_of(rel))
    context.route(prefix + "**", fulfill)


async def apply_cdn_async(context, cache_dir: Path, prefix: str = CDN_PREFIX) -> None:
    async def fulfill(route):
        rel = route.request.url.split(prefix)[-1].split("?")[0]
        f = Path(cache_dir) / rel
        if not (f.exists() and f.stat().st_size):
            if not _fetch_missing(route.request.url, f):
                await route.abort()
                return
        await route.fulfill(path=str(f), content_type=_ctype_of(rel))
    await context.route(prefix + "**", fulfill)


async def ensure_authstate_async(page, reload_limit: int = 3) -> bool:
    has = await page.evaluate("() => typeof window.authState !== 'undefined'")
    if not has:
        return True
    for _ in range(reload_limit):
        ok = await page.evaluate("() => !!(window.authState && window.authState.user && window.authState.user.id)")
        if ok:
            return True
        await page.reload(wait_until="domcontentloaded")
    return await page.evaluate("() => !!(window.authState && window.authState.user && window.authState.user.id)")


@contextlib.contextmanager
def trio_env(empty_dir: str | Path | None = None):
    saved = {k: os.environ.get(k) for k in TRIO_KEYS}
    empty = str(empty_dir or tempfile.mkdtemp(prefix="fe_env2_disc_"))
    Path(empty).mkdir(parents=True, exist_ok=True)
    os.environ["DISCOVERY_CACHE_PATH"] = empty
    os.environ["MINIDEPLOY_BASE_URL"] = "http://127.0.0.1:1"
    os.environ["UC__BASE_URL"] = "http://127.0.0.1:1"
    try:
        yield empty
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


@contextlib.contextmanager
def isolate_discovery(path: str | Path | None = None):
    saved = os.environ.get("DISCOVERY_CACHE_PATH")
    p = str(path or tempfile.mkdtemp(prefix="fe_env2_isodisc_"))
    Path(p).mkdir(parents=True, exist_ok=True)
    os.environ["DISCOVERY_CACHE_PATH"] = p
    try:
        yield p
    finally:
        if saved is None:
            os.environ.pop("DISCOVERY_CACHE_PATH", None)
        else:
            os.environ["DISCOVERY_CACHE_PATH"] = saved


def uc_token(payload: dict, secret: str, alg: str = "HS256") -> str:
    claims = {"exp": int(time.time()) + 3600, **payload}
    try:
        from jose import jwt as jose_jwt
        return jose_jwt.encode(claims, secret, algorithm=alg)
    except ImportError:
        pass
    try:
        import jwt as pyjwt
        return pyjwt.encode(claims, secret, algorithm=alg)
    except ImportError:
        raise RuntimeError(
            "uc_token 需要 python-jose 或 PyJWT 之一（沿用仓内既有依赖，canon 不新增）")


def ensure_authstate(page, reload_limit: int = 3) -> bool:
    has = page.evaluate("() => typeof window.authState !== 'undefined'")
    if not has:
        return True
    for _ in range(reload_limit):
        ok = page.evaluate("() => !!(window.authState && window.authState.user && window.authState.user.id)")
        if ok:
            return True
        page.reload(wait_until="domcontentloaded")
    return page.evaluate("() => !!(window.authState && window.authState.user && window.authState.user.id)")


@contextlib.contextmanager
def serve_app(app_module: str, port: int, cwd: str | Path = ".", health_path: str = "/health",
              env: dict | None = None, timeout: float = 30.0):
    if not (19000 <= port <= 19999):
        raise ValueError(f"serve_app 端口必须 19xxx 高位（got {port}）")
    env_full = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", app_module, "--port", str(port), "--host", "127.0.0.1"],
        cwd=str(cwd), env=env_full,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    deadline = time.time() + timeout
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(f"serve_app: {app_module} 提前退出 rc={proc.returncode}")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}{health_path}", timeout=2).read()
            ready = True
            break
        except Exception:
            time.sleep(0.3)
    if not ready:
        _kill_proc(proc)
        raise RuntimeError(f"serve_app: {app_module} {timeout}s 未就绪（health={health_path}）")
    try:
        yield f"http://127.0.0.1:{port}", proc
    finally:
        _kill_proc(proc)


def _kill_proc(proc: subprocess.Popen) -> None:
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except Exception:
            proc.kill()
        proc.wait(timeout=5)


def goto_app(page, url: str, ready_selector: str, timeout: int = 30000) -> None:
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    page.wait_for_selector(ready_selector, state="visible", timeout=timeout)


def wait_state(page, expr: str, timeout: int = 15000, arg: dict | None = None) -> bool:
    page.wait_for_function(expr, arg=arg or {}, timeout=timeout)
    return True


@contextlib.contextmanager
def iso_db(prefix: str = "fe_env2_db_", filename: str = "e2e.db"):
    d = Path(tempfile.mkdtemp(prefix=prefix))
    db = d / filename
    try:
        yield db
    finally:
        shutil.rmtree(d, ignore_errors=True)


def mock_bare(payload: dict) -> dict:
    return json.loads(json.dumps(payload))


def selfcheck() -> int:
    checks = []
    with tempfile.TemporaryDirectory() as td:
        ih = Path(td) / "index.html"
        ih.write_text(f'<script src="{CDN_PREFIX}x/y.js?v=1"></script>', encoding="utf-8")
        cache = ensure_cdn(ih, cache_dir=Path(td) / "cdn")
        checks.append(("ensure_cdn_cache_dir", cache.is_dir()))
    with trio_env():
        checks.append(("trio_all_set", all(os.environ.get(k) for k in TRIO_KEYS)))
    checks.append(("trio_restored", os.environ.get("UC__BASE_URL") is None))
    with iso_db() as db:
        checks.append(("iso_db_created", db.parent.name.startswith("fe_env2_db_")))
    with isolate_discovery() as iso_p:
        checks.append(("isolate_discovery_set", os.environ.get("DISCOVERY_CACHE_PATH") == iso_p))
        checks.append(("isolate_discovery_surgical", "UC__BASE_URL" not in os.environ))
    checks.append(("isolate_discovery_restored", "DISCOVERY_CACHE_PATH" not in os.environ))
    try:
        uc_token({"sub": "1"}, "s")
        checks.append(("uc_token_lib", True))
    except RuntimeError:
        checks.append(("uc_token_lib", False))
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print(f"  {'PASS' if ok else 'FAIL'} {n}")
    print(f"fe_env2 selfcheck: {len(checks) - len(bad)}/{len(checks)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selfcheck())
