#!/usr/bin/env python3
"""r19 沉默救援 E2E：失踪判定/absence 触达(通道捕获+幂等)/回归 return_block/suggest_adjust"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610")
API = BASE + "/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

USER = "cp_r19_e2e_" + str(int(time.time()))
PWD = "CpR19#x2026"
passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method: str, path: str, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=30) as resp:
        return json.loads(resp.read() or b"{}")


def shift(days_ago: int) -> str:
    import datetime
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def make_plan(days: int) -> list[dict]:
    return [
        {"day": i + 1, "title": f"r19 第{i+1}天", "description": "E2E", "tip": "",
         "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
        for i in range(days)
    ]


def create_ladder(token: str, start: str) -> int:
    ch = api("POST", "/challenges/confirm", {
        "title": "r19失踪阶梯", "category": "quit", "duration_days": 40,
        "start_date": start, "description": "E2E absence", "plan": make_plan(40),
        "source": "manual", "task_type": "counter", "target_value": 12.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    return int(ch["id"])


async def seed_day(challenge_id: int, user_id: str, date: str, value: float) -> None:
    from app.db.database import async_session, init_db
    from app.services.goal_rule_service import daily_target
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.streak_service import day_number_of
    from app.repositories.challenge_repository import ChallengeRepository

    await init_db()
    async with async_session() as session:
        ch = await ChallengeRepository().get_by_id(session, challenge_id)
        day_number = day_number_of(str(ch.start_date), date)
        await CheckInRepository().create(session, {
            "challenge_id": challenge_id, "user_id": user_id, "day_number": day_number,
            "status": "completed",
            "timestamp": __import__("datetime").datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(ch.unit),
            "target_value": float(daily_target(ch, day_number)),
            "goal_type": str(ch.goal_type), "direction": str(ch.direction),
            "completion_pct": 100.0,
        })
        await session.commit()


async def cleanup(challenge_ids: list[int]) -> None:
    from app.db.database import async_session, init_db
    from sqlalchemy import delete
    from app.models.checkin import AIInsight, CheckIn
    from app.models.challenge import Challenge

    await init_db()
    async with async_session() as session:
        if challenge_ids:
            await session.execute(delete(CheckIn).where(CheckIn.challenge_id.in_(challenge_ids)))
            await session.execute(delete(AIInsight).where(AIInsight.challenge_id.in_(challenge_ids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(challenge_ids)))
        await session.commit()


async def run_reminder_job(hour: int, captured: list[dict]) -> None:
    import app.services.reminder_service as reminder_mod

    class FakeClient:
        async def send_many(self, items):
            captured.extend(items)
            return [{"status": "sent"} for _ in items]

    reminder_mod.get_notify_client = lambda: FakeClient()
    await reminder_mod.send_checkin_reminders(current_hour=hour)


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    check("注册拿到token", bool(token) and bool(uid), str(st)[:120])

    start = shift(4)
    cid = create_ladder(token, start)
    check("创建减量阶梯(day5)", cid > 0, str(cid))
    asyncio.run(seed_day(cid, uid, start, 6.0))

    t0 = api("GET", f"/challenges/{cid}/today", token=token)
    a = t0.get("absence") or {}
    check("absence.absent_days=3(start=day1)", int(a.get("absent_days", 0)) == 3, str(a)[:140])
    check("absence.last_record_date=首日", a.get("last_record_date") == start, str(a.get("last_record_date")))
    check("absence.last_value=6", float(a.get("last_value", 0)) == 6.0, str(a.get("last_value")))
    check("absence.cap_now=10(day5)", float(a.get("cap_now", 0)) == 10.0, str(a.get("cap_now")))
    check("absence.today_checked=False", a.get("today_checked") is False, str(a.get("today_checked")))
    check("absence.can_shift", a.get("can_shift") is True, str(a.get("can_shift")))
    check("absence.suggest_adjust=False(6<=10)", a.get("suggest_adjust") is False, str(a.get("suggest_adjust")))
    check("slip块为None(昨天无记录)", not t0.get("slip"), str(t0.get("slip"))[:80])

    captured: list[dict] = []
    asyncio.run(run_reminder_job(20, captured))
    mine = [i for i in captured if str(i.get("user_id")) == uid and (i.get("data") or {}).get("absence_care")]
    others_absence = [i for i in captured if str(i.get("user_id")) != uid and (i.get("data") or {}).get("absence_care")]
    check("absence触达恰好1条(限本用户)", len(mine) == 1, f"mine={len(mine)} others={len(others_absence)}")
    if mine:
        item = mine[0]
        check("触达标题=3天没见了", "3 天没见了" in str(item.get("title", "")), str(item.get("title")))
        check("触达link带回挑战页", f"ch={cid}" in str(item.get("link", "")), str(item.get("link")))
        check("文案含今天上限10", "今天上限 10" in str(item.get("content", "")), str(item.get("content"))[:90])
        check("文案含少抽都在", "6 根都还在" in str(item.get("content", "")), str(item.get("content"))[:90])
        check("文案零羞辱词", all(w not in str(item.get("content", "")) for w in ("超了", "断了", "失败")), str(item.get("content"))[:90])

    captured2: list[dict] = []
    asyncio.run(run_reminder_job(20, captured2))
    mine2 = [i for i in captured2 if str(i.get("user_id")) == uid and (i.get("data") or {}).get("absence_care")]
    check("同episode幂等零重发", len(mine2) == 0, str(len(mine2)))

    ck = api("POST", f"/challenges/{cid}/checkin", {"value": 3}, token)
    rb = ck.get("return_block") or {}
    check("回归打卡return_block.absent_days=3", int(rb.get("absent_days", 0)) == 3, str(rb)[:140])
    check("return_block.cap_now=10", float(rb.get("cap_now", 0)) == 10.0, str(rb.get("cap_now")))
    check("return_block.last_value=6", float(rb.get("last_value", 0)) == 6.0, str(rb.get("last_value")))
    check("return_block.suggest_adjust=False", rb.get("suggest_adjust") is False, str(rb.get("suggest_adjust")))

    ck2 = api("POST", f"/challenges/{cid}/checkin", {"value": 2}, token)
    check("今日第二笔无return_block", not ck2.get("return_block"), str(ck2.get("return_block"))[:80])

    t1 = api("GET", f"/challenges/{cid}/today", token=token)
    check("打卡后absence块消失", not t1.get("absence"), str(t1.get("absence"))[:80])

    cid2 = create_ladder(token, shift(4))
    asyncio.run(seed_day(cid2, uid, shift(4), 15.0))
    t2 = api("GET", f"/challenges/{cid2}/today", token=token)
    a2 = t2.get("absence") or {}
    check("破戒量场景absence存在", int(a2.get("absent_days", 0)) == 3, str(a2)[:120])
    check("suggest_adjust=True(15>10)", a2.get("suggest_adjust") is True, str(a2.get("suggest_adjust")))
    ck3 = api("POST", f"/challenges/{cid2}/checkin", {"value": 5}, token)
    rb3 = ck3.get("return_block") or {}
    check("破戒回归suggest_adjust=True", rb3.get("suggest_adjust") is True, str(rb3)[:120])
    check("回归响应带avoided_total", int(rb3.get("avoided_total", -1)) == 0, str(rb3.get("avoided_total")))

    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail[:140]}")
    asyncio.run(cleanup([cid, cid2]))
    print("cleanup done (business rows purged by challenge ids)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    import urllib.error
    main()
