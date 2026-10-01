#!/usr/bin/env python3
"""ChallengePlanet 情境洞察闭环 E2E - 带情境打卡/补选情境/报表情境分布"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610/api/v1")
USER = "cp_ctx_" + str(int(time.time()))
PWD = "CpCtx#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def req(method: str, path: str, body: dict | None = None, token: str | None = None,
        timeout: int = 60):
    url = path if path.startswith("http") else BASE + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, json.loads(payload or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


print("== 1. 注册并登录一次性账号 ==")
st, body = req("POST", "/auth/register", {"username": USER, "password": PWD})
data = body.get("data") or body
token = data.get("access_token")
if not token:
    st, body = req("POST", "/auth/login", {"username": USER, "password": PWD})
    data = body.get("data") or body
    token = data.get("access_token")
check("拿到访问token", st == 200 and bool(token), f"st={st} body={str(body)[:160]}")

print("== 2. 创建减量挑战(戒烟) ==")
today = time.strftime("%Y-%m-%d")
plan = [
    {"day": i + 1, "title": f"戒烟第{i+1}天", "description": "记录今天抽的每根烟",
     "tip": "想抽时先喝水", "task_type": "counter", "target_value": 5.0,
     "unit": "根", "difficulty": 3, "steps": []}
    for i in range(14)
]
st, ch = req("POST", "/challenges/confirm", {
    "title": "情境洞察E2E戒烟",
    "category": "quit",
    "duration_days": 14,
    "start_date": today,
    "description": "带情境记录每次抽烟",
    "plan": plan,
    "source": "manual",
    "task_type": "counter",
    "target_value": 5.0,
    "unit": "根",
    "direction": "decrease",
    "goal_type": "soft",
}, token)
cid = ch.get("id") if isinstance(ch, dict) else None
check("创建挑战返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")

print("== 3. 带情境打卡 ==")
st, r1 = req("POST", f"/challenges/{cid}/checkin", {"value": 2.0, "context_tag": "work"}, token)
ck1 = (r1.get("checkin") or {}) if isinstance(r1, dict) else {}
check("打卡带context_tag=work", st == 200 and ck1.get("context_tag") == "work",
      f"st={st} body={str(r1)[:200]}")
check("today_total=2", float(r1.get("today_total", 0)) == 2.0, f"tt={r1.get('today_total')}")

print("== 4. 今日payload透出情境 ==")
st, today_view = req("GET", f"/challenges/{cid}/today", None, token)
rows = today_view.get("today_checkins") or []
check("today_checkins含context_tag", len(rows) == 1 and rows[0].get("context_tag") == "work",
      f"rows={str(rows)[:200]}")

print("== 5. 无情境打卡后补选情境(PATCH meta) ==")
st, r2 = req("POST", f"/challenges/{cid}/checkin", {"value": 1.0}, token)
ck2 = (r2.get("checkin") or {}) if isinstance(r2, dict) else {}
check("第二笔无情境", st == 200 and ck2.get("context_tag") == "", f"st={st}")
st, pr = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta",
             {"context_tag": "stress"}, token)
check("PATCH补选情境=stress", st == 200 and pr.get("context_tag") == "stress",
      f"st={st} body={str(pr)[:200]}")
st, _ = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta",
            {"context_tag": "party"}, token)
check("非法情境返回400", st == 400, f"st={st}")

print("== 6. 报表情境分布 ==")
st, dist = req("GET", f"/challenges/{cid}/report/context?days=30", None, token)
items = dist.get("items") or []
check("report/context返回200", st == 200, f"st={st}")
check("情境聚合work=2根/stress=1根",
      len(items) == 2 and items[0]["context_tag"] == "work" and float(items[0]["total_value"]) == 2.0
      and items[1]["context_tag"] == "stress" and float(items[1]["total_value"]) == 1.0,
      f"items={str(items)[:240]}")
check("dominant=work", dist.get("dominant") == "work", f"d={dist.get('dominant')}")
check("decrease洞察提到工作", "工作" in (dist.get("insight") or ""), f"i={dist.get('insight')}")
shares = [float(i.get("share_pct", 0)) for i in items]
check("占比合计≈100%", abs(sum(shares) - 100.0) < 0.2, f"shares={shares}")

print("== 7. 清理 ==")
st, _ = req("DELETE", f"/challenges/{cid}", None, token)
check("清理挑战", st == 200, f"st={st}")

print(f"\n=== 情境洞察闭环 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
for name, detail in failed:
    print(f"  FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
