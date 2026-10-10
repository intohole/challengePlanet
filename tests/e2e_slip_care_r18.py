#!/usr/bin/env python3
"""r18 破戒生命周期 E2E：slip 判定/晨间触达(通道捕获)/阶梯换挡预览+落库/守卫"""
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

USER = "cp_r18_e2e_" + str(int(time.time()))
USER_B = USER + "b"
PWD = "CpR18#x2026"
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
        {"day": i + 1, "title": f"r18 第{i+1}天", "description": "E2E", "tip": "",
         "task_type": "counter", "target_value": 12.0, "unit": "根", "difficulty": 3, "steps": []}
        for i in range(days)
    ]


def create_ladder(token: str, start: str) -> int:
    ch = api("POST", "/challenges/confirm", {
        "title": "r18破戒阶梯", "category": "quit", "duration_days": 30,
        "start_date": start, "description": "E2E slip", "plan": make_plan(30),
        "source": "manual", "task_type": "counter", "target_value": 12.0, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "goal_mode": "ceiling", "ladder_start": 12.0, "ladder_goal": 3.0,
        "ladder_interval": 2, "ladder_step": 1.0,
    }, token)
    return int(ch["id"])


def create_fixed(token: str) -> int:
    ch = api("POST", "/challenges/confirm", {
        "title": "r18固定挑战", "category": "build", "duration_days": 14,
        "start_date": shift(1), "description": "E2E", "plan": make_plan(14),
        "source": "manual", "task_type": "counter", "target_value": 5.0, "unit": "次",
        "direction": "increase", "goal_type": "hard",
    }, token)
    return int(ch["id"])


async def seed_over_day(challenge_id: int, user_id: str, date: str, value: float) -> None:
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
    from app.models.checkin import CheckIn
    from app.models.challenge import Challenge
    from app.repositories.checkin_repository import InsightRepository

    await init_db()
    async with async_session() as session:
        if challenge_ids:
            await session.execute(delete(CheckIn).where(CheckIn.challenge_id.in_(challenge_ids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(challenge_ids)))
            for cid in challenge_ids:
                row = await InsightRepository().get_by_type(session, cid, "slip_care")
                if row is not None:
                    await session.delete(row)
        await session.commit()


async def run_slip_care_job(captured: list[dict]) -> None:
    import app.services.slip_service as slip_mod

    class FakeClient:
        async def send_many(self, items):
            captured.extend(items)
            return [{"status": "sent"} for _ in items]

    slip_mod.get_notify_client = lambda: FakeClient()
    await slip_mod.send_slip_care()


def main() -> None:
    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d.get("access_token")
    uid = str((d.get("user") or {}).get("id") or "")
    check("注册拿到token", bool(token) and bool(uid), str(st)[:120])

    start = shift(2)
    cid = create_ladder(token, start)
    check("创建减量阶梯", cid > 0, str(cid))

    t0 = api("GET", f"/challenges/{cid}/today", token=token)
    check("day3今日上限=11(阶梯原样)", float(t0.get("today_target", 0)) == 11.0, str(t0.get("today_target")))
    check("无slip块(昨天没记录)", not t0.get("slip"), str(t0.get("slip"))[:80])

    asyncio.run(seed_over_day(cid, uid, shift(1), 15.0))

    t1 = api("GET", f"/challenges/{cid}/today", token=token)
    slip = t1.get("slip") or {}
    check("slip.yesterday_over", slip.get("yesterday_over") is True, str(slip)[:160])
    check("slip.over_amount=3(15-12)", float(slip.get("over_amount", 0)) == 3.0, str(slip.get("over_amount")))
    check("slip.yesterday_cap=12", float(slip.get("yesterday_cap", 0)) == 12.0, str(slip.get("yesterday_cap")))
    check("slip.episode_first(前天无记录=守住)", slip.get("episode_first") is True, str(slip.get("episode_first")))
    check("slip.today_checked=False", slip.get("today_checked") is False, str(slip.get("today_checked")))
    check("slip.can_shift", slip.get("can_shift") is True, str(slip.get("can_shift")))

    captured: list[dict] = []
    asyncio.run(run_slip_care_job(captured))
    check("触达恰好1条", len(captured) == 1, str(len(captured)))
    if captured:
        item = captured[0]
        check("触达user正确", str(item.get("user_id")) == uid, str(item.get("user_id")))
        check("深链带slip=1", "slip=1" in str(item.get("link", "")) and f"ch={cid}" in str(item.get("link", "")), str(item.get("link")))
        check("标题含超量", "超了 3" in str(item.get("title", "")), str(item.get("title")))
        check("文案含少抽资产", "都算数" in str(item.get("content", "")), str(item.get("content"))[:80])

    captured2: list[dict] = []
    asyncio.run(run_slip_care_job(captured2))
    check("同episode幂等零重发", len(captured2) == 0, str(len(captured2)))

    cid2 = create_ladder(token, shift(3))
    asyncio.run(seed_over_day(cid2, uid, shift(1), 14.0))
    asyncio.run(seed_over_day(cid2, uid, shift(2), 13.0))
    captured3: list[dict] = []
    asyncio.run(run_slip_care_job(captured3))
    check("连续破戒不再触达", len(captured3) == 0, str(len(captured3)))

    pv = api("POST", f"/challenges/{cid}/ladder-adjust", {"shift_days": 2, "preview": True}, token)
    check("预览today_cap=12", float(pv.get("today_cap", 0)) == 12.0, str(pv))
    check("预览毕业日顺延至+2", pv.get("goal_day") == 21, str(pv.get("goal_day")))
    check("预览不落库", bool(pv.get("preview")) and not pv.get("applied_at"), str(pv.get("preview")))
    t2 = api("GET", f"/challenges/{cid}/today", token=token)
    check("预览后today仍=11", float(t2.get("today_target", 0)) == 11.0, str(t2.get("today_target")))

    adj = api("POST", f"/challenges/{cid}/ladder-adjust", {"shift_days": 2}, token)
    check("落库today_cap=12", float(adj.get("today_cap", 0)) == 12.0, str(adj))
    check("total_shift=2", int(adj.get("total_shift_days", 0)) == 2, str(adj))
    check("毕业日已顺延", adj.get("graduation_date") == shift(-20) or adj.get("goal_day") == 21, str(adj.get("graduation_date")))

    t3 = api("GET", f"/challenges/{cid}/today", token=token)
    check("today上限已升到12", float(t3.get("today_target", 0)) == 12.0, str(t3.get("today_target")))
    j = t3.get("journey") or {}
    adjs = j.get("adjustments") or []
    check("journey换挡记录1条今天", len(adjs) == 1 and adjs[0].get("shift") == 2, str(adjs))
    check("journey.goal_date同步", str(j.get("goal_date")) == str(adj.get("graduation_date")), f"{j.get('goal_date')} vs {adj.get('graduation_date')}")

    ck = api("POST", f"/challenges/{cid}/checkin", {"value": 3}, token)
    check("换挡后打卡正常", bool(ck), str(ck)[:100])

    for bad in (0, 20):
        try:
            api("POST", f"/challenges/{cid}/ladder-adjust", {"shift_days": bad}, token)
            check(f"非法shift={bad}被拒", False, "no error")
        except urllib.error.HTTPError as e:
            check(f"非法shift={bad}被拒", e.code == 422, str(e.code))

    stb = api("POST", "/auth/register", {"username": USER_B, "password": PWD})
    token_b = ((stb.get("data") or stb).get("access_token"))
    try:
        api("POST", f"/challenges/{cid}/ladder-adjust", {"shift_days": 2}, token_b)
        check("越权换挡被拒", False, "no error")
    except urllib.error.HTTPError as e:
        check("越权换挡被拒", e.code == 404, str(e.code))

    fid = create_fixed(token)
    try:
        api("POST", f"/challenges/{fid}/ladder-adjust", {"shift_days": 2}, token)
        check("非阶梯换挡被拒", False, "no error")
    except urllib.error.HTTPError as e:
        check("非阶梯换挡被拒", e.code == 422, str(e.code))

    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail[:140]}")
    asyncio.run(cleanup([cid, cid2, fid]))
    print("cleanup done (business rows purged by challenge ids)")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    import urllib.error
    main()
