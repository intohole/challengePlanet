#!/usr/bin/env python3
"""ChallengePlanet Tier3 深度功能 E2E 测试 - 对话微调/里程碑/作息洞察/破戒陪伴"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://songguokr.com/challengePlanet"
API = f"{BASE}/api/v1"
USER, PWD = "cp_e2e", "CpE2e#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def req(method: str, path: str, body: dict | None = None, token: str | None = None,
        timeout: int = 150, raw: bool = False):
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


def sse_create(token: str, raw_input: str, adjust_hint: str = "") -> tuple[str, list[dict], dict]:
    url = f"{API}/challenges/nl-create"
    body = {"raw_input": raw_input}
    if adjust_hint:
        body["adjust_hint"] = adjust_hint
    r = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
    r.add_header("Content-Type", "application/json")
    r.add_header("Authorization", f"Bearer {token}")
    steps: list[str] = []
    plan: list[dict] = []
    parsed_info: dict = {}
    err = ""
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
    except Exception as e:
        err = str(e)
    return err or "ok", plan, parsed_info


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

print("== 2. 生成计划-对话微调(adjust_hint) ==")
today = time.strftime("%Y-%m-%d")
err, plan_orig, parsed = sse_create(token, "我想21天养成每天阅读30分钟的习惯")
check("原始生成计划非空", err == "ok" and len(plan_orig) >= 7,
      f"err={err} len={len(plan_orig)}")
err2, plan_adj, _ = sse_create(
    token, "我想21天养成每天阅读30分钟的习惯", adjust_hint="太难了，每天任务减半，改成15分钟"
)
check("带调整指令生成非空", err2 == "ok" and len(plan_adj) >= 7,
      f"err={err2} len={len(plan_adj)}")
diff_target = 0
for po, pa in zip(plan_orig[:21], plan_adj[:21]):
    vo = float((po.get("target_value") or 0) or 0)
    va = float((pa.get("target_value") or 0) or 0)
    if vo > 0 and va > 0 and va < vo:
        diff_target += 1
check("调整后目标值整体下调(至少3天)", diff_target >= 3,
      f"下调天数={diff_target}")

print("== 3. 确认创建调整后计划 ==")
duration = int(parsed.get("duration_days", 21))
st, ch = req("POST", "/challenges/confirm", {
    "title": parsed.get("title") or "21天阅读挑战",
    "category": parsed.get("category", "build"),
    "duration_days": duration,
    "start_date": today,
    "description": parsed.get("description", ""),
    "plan": plan_adj,
    "source": "manual",
}, token)
cid = ch.get("id")
check("确认创建返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")

print("== 4. 里程碑节奏(guidance) ==")
st, g = req("GET", f"/challenges/{cid}/guidance", token=token)
check("guidance返回", st == 200 and isinstance(g, dict), f"st={st} body={str(g)[:150]}")
check("guidance含next_milestone对象", isinstance(g.get("next_milestone"), dict),
      f"nm={g.get('next_milestone')}")
nm = g.get("next_milestone") or {}
check("next_milestone.day>0且<=total", 0 < int(nm.get("day", 0)) <= int(g.get("total_days", 30)),
      f"day={nm.get('day')} total={g.get('total_days')}")
check("next_milestone含tip与days_to_go",
      bool(nm.get("tip")) and isinstance(nm.get("days_to_go"), int),
      f"tip={nm.get('tip')} dtg={nm.get('days_to_go')}")
check("guidance含milestone_tip非空", bool(g.get("milestone_tip")), f"mt={g.get('milestone_tip', '')[:40]}")

print("== 5. 作息节奏洞察(report/hourly) ==")
st, hourly = req("GET", f"/challenges/{cid}/report/hourly?days=30", token=token)
check("小时分布返回24项", st == 200 and isinstance(hourly.get("items"), list) and len(hourly.get("items", [])) == 24,
      f"st={st} len={len(hourly.get('items', [])) if isinstance(hourly.get('items'), list) else 'NA'}")
check("小时分布含peak_hour", "peak_hour" in hourly, f"keys={list(hourly.keys())}")
check("小时分布insight含时段描述", bool(hourly.get("insight")) and ":00" in str(hourly.get("insight")),
      f"ins={hourly.get('insight', '')[:60]}")

print("== 6. 破戒陪伴(guidance.companion) ==")
st, ck = req("POST", f"/challenges/{cid}/checkin", {"mood": "good", "reflection": "阅读完成"}, token, timeout=90)
check("打卡成功", st == 200 and ck.get("checkin", {}).get("id"), f"st={st} body={str(ck)[:120]}")
st, g2 = req("GET", f"/challenges/{cid}/guidance", token=token)
comp = g2.get("companion") or {}
check("guidance含companion对象", isinstance(g2.get("companion"), dict),
      f"comp={g2.get('companion')}")
check("companion含score且0-100", isinstance(comp.get("score"), int) and 0 <= comp.get("score", -1) <= 100,
      f"score={comp.get('score')}")
check("companion.level合法", comp.get("level") in ("low", "medium", "high"),
      f"level={comp.get('level')}")
check("companion.reasons为列表", isinstance(comp.get("reasons"), list),
      f"reasons={comp.get('reasons')}")
check("companion.micro_action非空", bool(comp.get("micro_action")),
      f"ma={comp.get('micro_action', '')[:40]}")
check("companion.message非空", bool(comp.get("message")),
      f"msg={comp.get('message', '')[:40]}")

print("== 7. 断签高风险陪伴(连续中断场景) ==")
cid2 = cid
st, ck_miss = req("POST", f"/challenges/{cid2}/checkin", {"mood": "bad", "reflection": "今天状态不好"}, token, timeout=90)
check("bad心情打卡成功", st == 200, f"st={st}")
st, g3 = req("GET", f"/challenges/{cid2}/guidance", token=token)
comp3 = g3.get("companion") or {}
score3 = int(comp3.get("score", 0))
check("bad心情后风险分升高", score3 >= int(comp.get("score", 0)),
      f"before={comp.get('score')} after={score3}")
if score3 >= 35:
    check("中高风险微行动含5分钟/放低/重启",
          any(k in str(comp3.get("micro_action")) for k in ("5分钟", "放低", "重启", "最小")),
          f"ma={comp3.get('micro_action', '')[:40]}")
else:
    check("低风险微行动含保持", "保持" in str(comp3.get("micro_action")),
          f"ma={comp3.get('micro_action', '')[:40]}")

print("== 8. 无token鉴权 ==")
st, _ = req("GET", f"/challenges/{cid}/guidance")
check("guidance无token拦截", st in (401, 403), f"st={st}")

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
for name, detail in failed:
    print(f"FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
