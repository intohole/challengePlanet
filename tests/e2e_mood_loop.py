#!/usr/bin/env python3
"""ChallengePlanet 心情闭环 E2E - 带心情打卡/补选心情/adaptive触发/报表心情分布/反馈SSE"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610/api/v1")
USER = "cp_mood_" + str(int(time.time()))
PWD = "CpMood#2026x"
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


def req_sse(path: str, body: dict, token: str, timeout: int = 90) -> tuple[int, list[dict]]:
    url = path if path.startswith("http") else BASE + path
    data = json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, method="POST")
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", "ignore")
            events = []
            for line in text.splitlines():
                if line.startswith("data:"):
                    try:
                        events.append(json.loads(line[5:].strip()))
                    except Exception:
                        pass
            return resp.status, events
    except urllib.error.HTTPError as e:
        return e.code, []


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

print("== 2. 创建减量挑战(戒烟 counter) ==")
today = time.strftime("%Y-%m-%d")
plan = [
    {"day": i + 1, "title": f"戒烟第{i+1}天", "description": "记录今天抽的每根烟",
     "tip": "想抽时先喝水", "task_type": "counter", "target_value": 5.0,
     "unit": "根", "difficulty": 3, "steps": []}
    for i in range(14)
]
st, ch = req("POST", "/challenges/confirm", {
    "title": "心情闭环E2E戒烟", "category": "quit", "duration_days": 14,
    "start_date": today, "description": "带心情记录每根烟", "plan": plan,
    "source": "manual", "task_type": "counter", "target_value": 5.0,
    "unit": "根", "direction": "decrease", "goal_type": "soft",
}, token)
cid = ch.get("id") if isinstance(ch, dict) else None
check("创建挑战返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")

print("== 3. 带心情打卡 ==")
st, r1 = req("POST", f"/challenges/{cid}/checkin", {"value": 1.0, "mood": "bad", "context_tag": "work"}, token)
ck1 = (r1.get("checkin") or {}) if isinstance(r1, dict) else {}
check("打卡带mood=bad", st == 200 and ck1.get("mood") == "bad", f"st={st} body={str(r1)[:200]}")

print("== 4. 无心情打卡后 PATCH meta 补心情+情境 ==")
st, r2 = req("POST", f"/challenges/{cid}/checkin", {"value": 1.0}, token)
ck2 = (r2.get("checkin") or {}) if isinstance(r2, dict) else {}
check("第二笔无mood", st == 200 and (ck2.get("mood") or "") == "", f"st={st}")
st, pr = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta",
             {"mood": "bad"}, token)
check("PATCH补mood=bad", st == 200 and pr.get("mood") == "bad", f"st={st} body={str(pr)[:200]}")
st, pr = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta",
             {"context_tag": "stress"}, token)
check("PATCH补context不覆盖mood", st == 200 and pr.get("mood") == "bad" and pr.get("context_tag") == "stress",
      f"st={st} body={str(pr)[:200]}")
st, _ = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta", {"mood": "angry"}, token)
check("非法mood返回400", st == 400, f"st={st}")
st, _ = req("PATCH", f"/challenges/{cid}/checkins/{ck2.get('id')}/meta", {}, token)
check("空patch返回400", st == 400, f"st={st}")

print("== 5. 连续2次bad触发adaptive减负建议 ==")
st, r3 = req("POST", f"/challenges/{cid}/checkin", {"value": 1.0, "mood": "bad"}, token)
sug = {}
for _ in range(15):
    time.sleep(2)
    st, ad = req("GET", f"/challenges/{cid}/adaptive/pending", None, token)
    sug = (ad.get("suggestion") or {}) if isinstance(ad, dict) else {}
    if sug.get("kind") == "lighten":
        break
check("adaptive减负建议已生成", st == 200 and sug.get("kind") == "lighten",
      f"st={st} body={str(ad)[:240]}")

print("== 6. 报表心情分布 ==")
st, r4 = req("POST", f"/challenges/{cid}/checkin", {"value": 1.0, "mood": "good"}, token)
check("good打卡成功", st == 200, f"st={st} body={str(r4)[:160]}")
st, dist = req("GET", f"/challenges/{cid}/report/mood?days=30", None, token)
items = dist.get("items") or []
check("report/mood返回200", st == 200, f"st={st}")
check("心情聚合bad=3排首位", len(items) >= 2 and items[0]["mood"] == "bad" and items[0]["checkin_count"] == 3,
      f"items={str(items)[:240]}")
check("bad占比75%", abs(float(items[0].get("share_pct", 0)) - 75.0) < 0.2,
      f"share={items[0].get('share_pct') if items else '-'}")
check("good占比25%", abs(float(items[1].get("share_pct", 0)) - 25.0) < 0.2,
      f"share={items[1].get('share_pct') if len(items) > 1 else '-'}")

print("== 7. 反馈SSE流式端点 ==")
st, events = req_sse(f"/challenges/{cid}/feedback/stream", {"checkin_id": ck1.get("id")}, token)
types = [e.get("type") for e in events]
dones = [e for e in events if e.get("type") == "done"]
check("SSE返回200且有done", st == 200 and len(dones) == 1, f"st={st} types={types[:8]}")
content = (dones[-1].get("content") or "") if dones else ""
check("done.content非空", len(content) >= 6, f"content={content[:80]}")
st, cks = req("GET", f"/challenges/{cid}/checkins", None, token)
fb_rows = [c for c in (cks if isinstance(cks, list) else []) if c.get("id") == ck1.get("id")]
check("反馈已写库", bool(fb_rows) and bool(fb_rows[0].get("ai_feedback")), f"rows={str(fb_rows)[:160]}")
st, events2 = req_sse(f"/challenges/{cid}/feedback/stream", {"checkin_id": ck1.get("id")}, token)
dones2 = [e for e in events2 if e.get("type") == "done"]
check("二次请求走缓存", st == 200 and len(dones2) == 1 and dones2[0].get("cached") is True
      and not [e for e in events2 if e.get("type") == "token"],
      f"types={[e.get('type') for e in events2][:8]}")

print("== 8. 清理 ==")
st, _ = req("DELETE", f"/challenges/{cid}", None, token)
check("清理挑战", st == 200, f"st={st}")

print(f"\n=== 心情闭环 E2E: PASS {len(passed)} / FAIL {len(failed)} ===")
for name, detail in failed:
    print(f"  FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
