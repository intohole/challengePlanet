#!/usr/bin/env python3
"""r20 HTTP 端到端：companion-status 与 today 口径一致（load_valid_dates 唯一真源，今天不计入 completed_days）"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8821"
API = BASE + "/api/v1"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

USER = "cp_r20_e2e_" + str(int(time.time()))
PWD = "CpR20#x2026"
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
        {"day": i + 1, "title": f"r20 第{i+1}天", "description": "E2E", "tip": "",
         "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
        for i in range(days)
    ]


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


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    check("注册拿到token", bool(token) and bool(uid), str(st)[:100])
    if not token:
        sys.exit(1)

    start = shift(4)
    ch = api("POST", "/challenges/confirm", {
        "title": "r20口径统一阶梯", "category": "quit", "duration_days": 40,
        "start_date": start, "description": "E2E companion r20", "plan": make_plan(40),
        "source": "manual", "task_type": "counter", "target_value": 15.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    cid = int(ch["id"])
    for i, v in ((4, 12.0), (3, 12.0), (2, 11.0), (1, 11.0)):
        asyncio.run(seed_day(cid, uid, shift(i), v))
    print(f"  seeded challenge {cid} days {shift(4)}..{shift(1)}")

    comp = api("GET", f"/challenges/{cid}/companion-status", token=token)
    today = api("GET", f"/challenges/{cid}/today", token=token)
    check("companion completed_days=4(今天不计入)", comp.get("completed_days") == 4, str(comp))
    check("companion streak=4", comp.get("streak") == 4, str(comp))
    check("companion phase=adaptation", comp.get("phase") == "adaptation", str(comp))
    check("companion risk=low", comp.get("risk_level") == "low", str(comp))
    check("口径一致: streak==today.streak", comp.get("streak") == today.get("streak"),
          f"comp={comp.get('streak')} today={today.get('streak')}")
    check("cap补全计入: completed>原始打卡0天缺口", comp.get("completed_days") == 4 and today.get("streak") == 4,
          f"comp={comp.get('completed_days')} today.streak={today.get('streak')}")

    asyncio.run(seed_day(cid, uid, shift(0), 10.0))
    comp2 = api("GET", f"/challenges/{cid}/companion-status", token=token)
    today2 = api("GET", f"/challenges/{cid}/today", token=token)
    check("打卡后 completed_days 仍=4", comp2.get("completed_days") == 4, str(comp2))
    check("打卡后 streak 仍=4(今天不计入valid)", comp2.get("streak") == 4, str(comp2))
    check("打卡后口径一致: streak==today.streak", comp2.get("streak") == today2.get("streak"),
          f"comp={comp2.get('streak')} today={today2.get('streak')}")

    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail[:140]}")
    asyncio.run(cleanup([cid]))
    print("cleanup done")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
