#!/usr/bin/env python3
"""ChallengePlanet E2E 全链路测试 - 公网域名"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://songguokr.com/challengeplanet"
API = f"{BASE}/api/v1"
USER, PWD = "cp_e2e", "CpE2e#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def req(method: str, path: str, body: dict | None = None, token: str | None = None,
        timeout: int = 30, raw: bool = False):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload or b"{}"))
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


print("== 1. 登录 ==")
st, body = req("POST", "/auth/login", {"username": USER, "password": PWD})
data = body.get("data") or body
token = data.get("access_token")
check("登录返回token", st == 200 and bool(token), f"st={st} body={str(body)[:200]}")

print("== 2. SSE流式创建预览 ==")
url = f"{API}/challenges/nl-create"
r = urllib.request.Request(url, data=json.dumps({"raw_input": "我想21天养成每天阅读30分钟的习惯"}).encode(), method="POST")
r.add_header("Content-Type", "application/json")
r.add_header("Authorization", f"Bearer {token}")
steps: list[str] = []
plan: list[dict] = []
suggestions: list[str] = []
parsed_info: dict = {}
sse_fail = ""
try:
    with urllib.request.urlopen(r, timeout=150) as resp:
        buf = b""
        for chunk in iter(lambda: resp.read(1024), b""):
            buf += chunk
            while b"\n\n" in buf:
                line, buf = buf.split(b"\n\n", 1)
                line = line.decode("utf-8", "ignore").strip()
                if line.startswith("data:"):
                    payload = json.loads(line[5:].strip())
                    step = payload.get("step", "")
                    if step and step not in steps:
                        steps.append(step)
                    if step == "parsed":
                        parsed_info = payload.get("parsed", {})
                    if step == "preview":
                        plan = payload.get("plan", [])
                        suggestions = payload.get("suggestions", [])
except Exception as e:
    sse_fail = str(e)
check("SSE步骤齐全(parsing/parsed/planning/preview)",
      all(s in steps for s in ("parsing", "parsed", "planning", "preview")), f"steps={steps} err={sse_fail}")
check("SSE计划非空且含day/title", len(plan) > 0 and all("day" in d and "title" in d for d in plan),
      f"plan_len={len(plan)}")
check("SSE解析出标题", bool(parsed_info.get("title")), f"parsed={parsed_info}")

print("== 3. 确认创建 ==")
duration = int(parsed_info.get("duration_days", 21))
st, ch = req("POST", "/challenges/confirm", {
    "title": parsed_info.get("title") or "21天阅读挑战",
    "category": parsed_info.get("category", "build"),
    "duration_days": duration,
    "description": parsed_info.get("description", ""),
    "plan": plan,
    "source": "manual",
}, token)
cid = ch.get("id")
check("确认创建返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")
check("响应含mercy字段", isinstance(ch.get("mercy"), dict), f"mercy={ch.get('mercy')}")

print("== 4. 列表与今日任务 ==")
st, lst = req("GET", "/challenges", token=token)
items = lst if isinstance(lst, list) else []
mine = [c for c in items if c.get("id") == cid]
check("列表包含新挑战", bool(mine), f"len={len(items)}")
check("列表项today_checked=False", mine and mine[0].get("today_checked") is False, "")
st, today = req("GET", f"/challenges/{cid}/today", token=token)
check("今日任务day_number=1", today.get("day_number") == 1, f"day={today.get('day_number')}")
check("今日任务标题来自计划", today.get("task_title") == str(plan[0].get("title", "")) if plan else False,
      f"task_title={today.get('task_title')} plan0={plan[0].get('title') if plan else None}")
st, notfound = req("GET", "/challenges/999999/today", token=token)
check("他人/不存在挑战返回404", st == 404, f"st={st}")

print("== 5. 打卡 ==")
st, ck = req("POST", f"/challenges/{cid}/checkin", {"mood": "good", "reflection": "第一天，读了30分钟非虚构"}, token, timeout=90)
check("打卡成功", st == 200 and ck.get("checkin", {}).get("id"), f"st={st} body={str(ck)[:200]}")
check("打卡获得积分", ck.get("points_earned", 0) > 0, f"points={ck.get('points_earned')}")
check("streak=1", ck.get("streak") == 1, f"streak={ck.get('streak')}")
check("AI反馈非空", bool(ck.get("ai_feedback")), "")
st, ck2 = req("POST", f"/challenges/{cid}/checkin", {"mood": "good", "reflection": "重复"}, token)
check("重复打卡幂等already_checked", ck2.get("already_checked") is True and ck2.get("points_earned") == 0,
      f"body={str(ck2)[:150]}")

print("== 6. 补打卡编辑 ==")
st, patched = req("PATCH", f"/challenges/{cid}/checkin/today", {"mood": "great", "reflection": "更新：实际读了45分钟"}, token, timeout=90)
check("PATCH更新心得", st == 200 and patched.get("reflection") == "更新：实际读了45分钟", f"st={st}")

print("== 7. 积分 ==")
st, summary = req("GET", "/points/summary", token=token)
check("积分总额>0", summary.get("total", 0) > 0, f"total={summary.get('total')}")
check("本周积分>0且week_key存在", summary.get("week_points", 0) > 0 and bool(summary.get("week_key")), "")
st, ledger = req("GET", "/points/ledger", token=token)
check("流水非空", isinstance(ledger, list) and len(ledger) > 0, f"len={len(ledger) if isinstance(ledger, list) else 'NA'}")
st, ledger_neg = req("GET", "/points/ledger?limit=-1", token=token)
check("负数limit被钳制", isinstance(ledger_neg, list) and len(ledger_neg) <= 100, "")

print("== 8. 宽容机制 ==")
st, mercy = req("GET", f"/challenges/{cid}/mercy", token=token)
check("补签剩余2次", mercy.get("mend_left_this_month") == 2, f"mercy={mercy}")
check("冻结剩余1次", mercy.get("freeze_left_this_week") == 1, "")
st, frz = req("POST", f"/challenges/{cid}/freeze", {"date": today.get("date")}, token)
check("冻结今天成功", st == 200 and frz.get("cost") == 0, f"st={st} body={frz}")
st, mercy2 = req("GET", f"/challenges/{cid}/mercy", token=token)
check("冻结后剩余0次", mercy2.get("freeze_left_this_week") == 0, f"={mercy2.get('freeze_left_this_week')}")
st, mend_future = req("POST", f"/challenges/{cid}/mend", {"date": today.get("date")}, token)
check("补签今天被拒绝400", st == 400, f"st={st}")

print("== 9. 小队 ==")
st, squad = req("POST", "/squads", {"name": "E2E互助组", "nickname": "E2E测试"}, token)
sid = squad.get("id")
invite = squad.get("invite_code")
check("创建小队返回邀请码", st == 200 and bool(invite), f"st={st} body={str(squad)[:150]}")
st, joined = req("POST", "/squads/join", {"invite_code": invite, "nickname": "E2E测试"}, token)
check("重复加入幂等", st == 200 and joined.get("id") == sid, f"st={st}")
st, board = req("GET", f"/squads/{sid}/board", token=token)
members = board.get("members", [])
check("看板1名成员且今日已打卡", len(members) == 1 and members[0].get("checked_today") is True,
      f"members={members}")
st, nudge_self = req("POST", f"/squads/{sid}/nudge", {"to_user_id": members[0]["user_id"] if members else "x"}, token)
check("戳自己被拒绝400", st == 400, f"st={st}")
st, bad_join = req("POST", "/squads/join", {"invite_code": "deadbeef00", "nickname": "x"}, token)
check("无效邀请码400", st == 400, f"st={st}")

print("== 10. 排行榜 ==")
st, lb = req("GET", "/leaderboard/weekly", token=token)
entries = lb.get("entries", [])
check("全球周榜含自己", any(str(e.get("user_id")) for e in entries), f"entries={entries[:3]}")
st, lb_squad = req("GET", f"/leaderboard/weekly?scope=squad&squad_id={sid}", token=token)
check("小队周榜有昵称", bool(lb_squad.get("entries")) and bool(lb_squad["entries"][0].get("nickname")),
      f"={lb_squad.get('entries')}")
st, lb_forbidden = req("GET", "/leaderboard/weekly?scope=squad&squad_id=999999", token=token)
check("非成员查小队榜403", st in (400, 403), f"st={st}")

print("== 11. 分享 ==")
st, sd = req("GET", f"/challenges/{cid}/share-data", token=token)
share_token = sd.get("share_token")
check("share-data含token与quote", bool(share_token) and "share_quote" in sd, f"keys={list(sd.keys())}")
st, pub = req("GET", f"/share/{share_token}")
check("token公开分享可查", st == 200 and pub.get("challenge_id") == cid, f"st={st}")
st, enum_gone = req("GET", f"/challenges/{cid}/share")
check("无鉴权ID分享端点已移除(404)", st == 404, f"st={st}")

print("== 12. portal/today ==")
st, portal = req("GET", "/portal/today", token=token)
check("portal返回date与items", st == 200 and bool(portal.get("date")) and isinstance(portal.get("items"), list),
      f"st={st} body={str(portal)[:200]}")
check("portal待打卡计数正确", portal.get("pending_count") == sum(1 for i in portal.get("items", []) if not i.get("checked")),
      f"pending={portal.get('pending_count')}")

print("== 13. 周报与洞察 ==")
st, weekly = req("GET", f"/challenges/{cid}/weekly-report", token=token)
check("周报结构正确", st == 200 and "week_checkins" in weekly and weekly.get("week_checkins") >= 1,
      f"={weekly}")
st, insights = req("GET", f"/challenges/{cid}/insights", token=token)
check("洞察列表可查", st == 200 and isinstance(insights, list), f"st={st}")

print("== 14. 无token鉴权拦截 ==")
st, _ = req("GET", "/challenges")
check("无token 401/403", st in (401, 403), f"st={st}")
st, _ = req("GET", "/points/summary")
check("points无token拦截", st in (401, 403), f"st={st}")

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
for name, detail in failed:
    print(f"FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
