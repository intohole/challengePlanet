#!/usr/bin/env python3
"""ChallengePlanet 二级打卡 E2E 回归 - 多次打卡/撤销/报表体系/校验（sub_goal 已随 c71048b 移除）"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
USER = "cp_t2_" + str(int(time.time()))
PWD = "CpT2#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def req(method: str, path: str, body: dict | None = None, token: str | None = None,
        timeout: int = 60):
    url = path if path.startswith("http") else API + path
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


print("== 1. 注册并登录 ==")
st, body = req("POST", "/auth/register", {"username": USER, "password": PWD})
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
    "title": "二级打卡回归戒烟", "category": "quit", "duration_days": 14,
    "start_date": today, "description": "多次打卡+报表回归", "plan": plan,
    "source": "manual", "task_type": "counter", "target_value": 5.0,
    "unit": "根", "direction": "decrease", "goal_type": "soft",
}, token)
cid = ch.get("id") if isinstance(ch, dict) else None
check("创建减量挑战返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")
check("挑战direction=decrease", ch.get("direction") == "decrease", f"dir={ch.get('direction')}")
check("挑战goal_type=soft", ch.get("goal_type") == "soft", f"gt={ch.get('goal_type')}")

print("== 3. 一天多次打卡 ==")
st, r1 = req("POST", f"/challenges/{cid}/checkin", {"value": 2.0, "context_tag": "work"}, token)
check("第1笔=2根", st == 200 and float(r1.get("today_total", 0)) == 2.0, f"st={st}")
st, r2 = req("POST", f"/challenges/{cid}/checkin", {"value": 3.0}, token)
check("第2笔累计=5根", st == 200 and float(r2.get("today_total", 0)) == 5.0, f"tt={r2.get('today_total')}")
check("软超标记", r2.get("is_soft_exceeded") in (True, False), f"ise={r2.get('is_soft_exceeded')}")
ck2 = r2.get("checkin") or {}
check("打卡响应含forecast", "forecast" in r2, f"keys={list(r2.keys())[:12]}")

print("== 4. 删除一笔打卡 ==")
st, _ = req("DELETE", f"/challenges/{cid}/checkins/{ck2.get('id')}", None, token)
check("删除返回200", st == 200, f"st={st}")
st, tv = req("GET", f"/challenges/{cid}/today", None, token)
rows = tv.get("today_checkins") or []
check("删除后today_total=2", float(tv.get("today_total", -1)) == 2.0, f"tt={tv.get('today_total')}")
check("剩余记录数=1", len(rows) == 1, f"len={len(rows)}")
check("记录带context_tag", rows and rows[0].get("context_tag") == "work", f"rows={str(rows)[:160]}")

print("== 5. 报表-总览 ==")
st, ov = req("GET", f"/challenges/{cid}/report/overview", token=token)
check("总览返回", st == 200 and isinstance(ov, dict), f"st={st}")
check("总览today_total=2.0", float(ov.get("today_total", 0)) == 2.0, f"tt={ov.get('today_total')}")
check("总览含streak/baseline/peak_hour",
      all(k in ov for k in ("streak", "dynamic_baseline", "peak_hour")), f"keys={list(ov.keys())[:12]}")
check("总览insight非空", bool(ov.get("insight")), f"ins={str(ov.get('insight'))[:60]}")

print("== 6. 报表-时段/趋势/热力/完成率/情境 ==")
st, hourly = req("GET", f"/challenges/{cid}/report/hourly?days=7", token=token)
check("时段分布24项", st == 200 and len(hourly.get("items", [])) == 24, f"st={st}")
check("时段分布含peak_hour", "peak_hour" in hourly, "")
st, ctx = req("GET", f"/challenges/{cid}/report/context?days=30", token=token)
check("情境分布聚合work=2", st == 200 and ctx.get("items") and
      ctx["items"][0]["context_tag"] == "work" and float(ctx["items"][0]["total_value"]) == 2.0,
      f"items={str(ctx.get('items'))[:160]}")
st, trend = req("GET", f"/challenges/{cid}/report/trend?days=30", token=token)
check("趋势30点", st == 200 and len(trend.get("points", [])) == 30, f"st={st}")
check("趋势含trend_direction", "trend_direction" in trend, "")
st, heat = req("GET", f"/challenges/{cid}/report/heatmap", token=token)
check("热力图cells非空", st == 200 and len(heat.get("cells", [])) > 0, f"st={st}")
st, comp = req("GET", f"/challenges/{cid}/report/completion?period=month", token=token)
check("完成率含rate/soft_exceed", st == 200 and
      all(k in comp for k in ("completion_rate", "soft_exceed_days", "hard_exceed_days")), f"st={st}")

print("== 7. 参数校验与边界 ==")
st, _ = req("GET", f"/challenges/{cid}/report/completion?period=invalid", token=token)
check("非法period被拒绝422", st == 422, f"st={st}")
st, _ = req("GET", f"/challenges/{cid}/report/hourly?days=200", token=token)
check("days超上限被拒绝422", st == 422, f"st={st}")
st, _ = req("POST", "/challenges/999999/checkin", {"value": 1.0}, token)
check("不存在挑战打卡返回400", st == 400, f"st={st}")
st, _ = req("PATCH", f"/challenges/{cid}/checkins/999999/meta", {"context_tag": "home"}, token)
check("PATCH不存在记录返回400", st == 400, f"st={st}")

print("== 8. 增量挑战与hard目标 ==")
plan2 = [
    {"day": i + 1, "title": f"喝水第{i+1}天", "description": "喝够8杯", "tip": "随手记",
     "task_type": "counter", "target_value": 8.0, "unit": "杯", "difficulty": 2, "steps": []}
    for i in range(14)
]
st, ch2 = req("POST", "/challenges/confirm", {
    "title": "二级打卡回归喝水", "category": "health", "duration_days": 14,
    "start_date": today, "description": "增量hard目标", "plan": plan2,
    "source": "manual", "task_type": "counter", "target_value": 8.0,
    "unit": "杯", "direction": "increase", "goal_type": "hard",
}, token)
cid2 = ch2.get("id") if isinstance(ch2, dict) else None
check("创建增量挑战返回id", st == 200 and isinstance(cid2, int), f"st={st}")
st, r3 = req("POST", f"/challenges/{cid2}/checkin", {"value": 3.0}, token)
check("增量打卡累计=3", st == 200 and float(r3.get("today_total", 0)) == 3.0, f"tt={r3.get('today_total')}")
check("hard目标不触发软超", r3.get("is_soft_exceeded") is False, f"ise={r3.get('is_soft_exceeded')}")
st, _ = req("DELETE", f"/challenges/{cid2}", None, token)
check("清理增量挑战", st == 200, f"st={st}")

print("== 9. 清理 ==")
st, _ = req("DELETE", f"/challenges/{cid}", None, token)
check("清理减量挑战", st == 200, f"st={st}")

print(f"\n=== 二级打卡回归 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
for name, detail in failed:
    print(f"  FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
