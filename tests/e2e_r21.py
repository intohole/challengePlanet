"""r21 浏览器/API E2E：召回漏斗四段+rescue 止血首发门槛+静默守披露+受众净化 fail-open。

本地 8610 真库真 UC；触达通道用捕获型假 client（本工作区既定形态），job 的
圈定/门槛/落痕逻辑真跑真库。造数按 challenge id 精确清理。
"""
from __future__ import annotations

import asyncio
import datetime
import json
import sys
import time
import urllib.request

sys.path.insert(0, ".")

BASE = "http://127.0.0.1:8610"
API = BASE + "/api/v1"
STAMP = str(int(time.time()))[-6:]
USER = "cp_r21_e2e_" + STAMP
PWD = "CpR21#x2026"

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def api(method, path, body=None, token=None):
    r = urllib.request.Request(API + path, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(r, data=data, timeout=20) as resp:
        return json.loads(resp.read())


def shift(days_ago):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


class FakeNotify:
    def __init__(self):
        self.sent: list[dict] = []

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return {"status": "sent", "id": len(self.sent)}

    async def send_many(self, items):
        out = []
        for item in items:
            out.append(await self.send(**item))
        return out


def make_challenge(token, title, start_days_ago=4, cap_mode=True):
    if cap_mode:
        body = {
            "title": title, "category": "quit", "duration_days": 40,
            "start_date": shift(start_days_ago), "source": "manual", "task_type": "counter",
            "target_value": 15.0, "unit": "根", "direction": "decrease", "goal_type": "soft",
            "goal_rule": "ladder", "goal_mode": "ceiling", "ladder_start": 12.0,
            "ladder_goal": 3.0, "ladder_interval": 2, "ladder_step": 1.0,
        }
    else:
        body = {
            "title": title, "category": "learn", "duration_days": 40,
            "start_date": shift(start_days_ago), "source": "manual", "task_type": "counter",
            "target_value": 20.0, "unit": "个", "direction": "increase", "goal_type": "hard",
            "goal_rule": "fixed", "goal_mode": "floor",
        }
    ch = api("POST", "/challenges/confirm", body, token)
    return int(ch["id"])


async def seed_day(challenge_id, user_id, date, value):
    from app.db.database import async_session, init_db
    from app.repositories.challenge_repository import ChallengeRepository
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.goal_rule_service import daily_target
    from app.services.streak_service import day_number_of
    await init_db()
    async with async_session() as session:
        c = await ChallengeRepository().get_by_id(session, challenge_id)
        dn = day_number_of(str(c.start_date), date)
        await CheckInRepository().create(session, {
            "challenge_id": challenge_id, "user_id": user_id, "day_number": dn,
            "status": "completed",
            "timestamp": datetime.datetime.strptime(date + " 21:30", "%Y-%m-%d %H:%M"),
            "date": date, "value": value, "unit": str(c.unit),
            "target_value": float(daily_target(c, dn)), "goal_type": str(c.goal_type),
            "direction": str(c.direction), "completion_pct": 100.0,
        })
        await session.commit()


async def db_cleanup(challenge_ids):
    from app.db.database import async_session, init_db
    from sqlalchemy import delete
    from app.db.database import Base  # noqa: F401
    from app.models.checkin import AIInsight, CheckIn
    from app.models.challenge import Challenge
    from app.models.recall import RecallEvent
    await init_db()
    async with async_session() as session:
        if challenge_ids:
            await session.execute(delete(CheckIn).where(CheckIn.challenge_id.in_(challenge_ids)))
            await session.execute(delete(AIInsight).where(AIInsight.challenge_id.in_(challenge_ids)))
            await session.execute(delete(RecallEvent).where(RecallEvent.challenge_id.in_(challenge_ids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(challenge_ids)))
        await session.commit()


def run_job_with_fake_notify(monkey_target="app.services.reminder_service"):
    """在进程内以捕获通道真跑 reminder job（真库圈定/门槛/落痕）。"""
    mod = __import__(monkey_target, fromlist=["get_notify_client"])
    fake = FakeNotify()
    mod.get_notify_client = lambda: fake
    asyncio.run(mod.send_checkin_reminders(current_hour=20))
    return fake


def main():
    import os
    os.environ.setdefault("REMINDER_GUARD_OFF", "1")

    st = api("POST", "/auth/register", {"username": USER, "password": PWD})
    d = st.get("data") or st
    token = d["access_token"]
    uid = str((d.get("user") or {}).get("id"))
    check("R0 注册+token", bool(token))

    # ---------- S1 rescue 止血：missed=2 静默（非 cap 打卡类走 rescue 通道）----------
    cid_a = make_challenge(token, "r21止血A", cap_mode=False)
    asyncio.run(seed_day(cid_a, uid, shift(4), 5.0))
    asyncio.run(seed_day(cid_a, uid, shift(3), 6.0))  # 最后记录在 3 天前→断 2 天
    fake = run_job_with_fake_notify()
    rescue_titles = [s["title"] for s in fake.sent if "星轨还在" in str(s.get("title", ""))]
    mine = [s for s in fake.sent if str(s.get("user_id")) == uid]
    check("S1 断2天零催促(首发门槛)", all("星轨还在" not in str(s.get("title", "")) for s in mine), str([s.get("title") for s in mine]))

    # ---------- S2 missed≥3 首发+落痕 ----------
    cid_b = make_challenge(token, "r21止血B", start_days_ago=4, cap_mode=False)
    asyncio.run(seed_day(cid_b, uid, shift(4), 5.0))  # 仅 day1 记录→断 3 天(每日档恒发)
    fake2 = run_job_with_fake_notify()
    mine2 = [s for s in fake2.sent if str(s.get("user_id")) == uid]
    rescues = [s for s in mine2 if "星轨还在" in str(s.get("title", ""))]
    check("S2 断4天首发催促", len(rescues) == 1, str([s.get("title") for s in mine2]))
    async def _insights():
        import sqlite3
        conn = sqlite3.connect("data/challenge.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT content FROM ai_insights WHERE challenge_id=? AND insight_type='rescue_care'",
            (cid_b,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    marks = asyncio.run(_insights())
    check("S2 rescue_care 落痕(先发送后落痕)", len(marks) == 1 and "missed_days" in marks[0]["content"], str(marks))

    # ---------- S3 recall 漏斗 HTTP 真链 ----------
    cid_c = make_challenge(token, "r21漏斗C", start_days_ago=5)
    asyncio.run(seed_day(cid_c, uid, shift(5), 15.0))
    r1 = api("POST", "/recall/track", {"challenge_id": cid_c, "channel": "absence", "stage": "arrived"}, token)
    check("S3 track arrived", bool(r1.get("ok")), str(r1))
    r2 = api("POST", "/recall/track", {"challenge_id": cid_c, "channel": "bad", "stage": "seen"}, token)
    check("S3 非法 channel 拒收", r2.get("ok") is False, str(r2))
    r3 = api("POST", "/recall/track", {"challenge_id": cid_c, "channel": "absence", "stage": "seen"}, token)
    check("S3 track seen", bool(r3.get("ok")), str(r3))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        ctx.add_init_script(f"window.localStorage.setItem('uc_access_token', '{token}')")
        page = ctx.new_page()
        page.goto(BASE + "/?ch=" + str(cid_c) + "&rc=absence", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        ss = page.evaluate("Object.fromEntries(Object.entries(sessionStorage).filter(([k])=>k.startsWith('cp_rk')))")
        arrived_keys = [k for k in ss if "_arrived_" in k]
        seen_keys = [k for k in ss if "_seen_" in k]
        check("S3 前端 arrived 上报(每日去重)", len(arrived_keys) >= 1, str(list(ss.keys())))
        check("S3 前端 seen 上报", len(seen_keys) >= 1, str(list(ss.keys())))
        browser.close()
    api("POST", f"/challenges/{cid_c}/checkin", {"value": 1, "context_tag": "", "mood": ""}, token)
    async def _funnel_rows():
        import sqlite3
        conn = sqlite3.connect("data/challenge.db")
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT stage, channel, COUNT(*) n FROM recall_events WHERE challenge_id=? GROUP BY stage, channel",
            (cid_c,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    ev = asyncio.run(_funnel_rows())
    ev_map = {(r["channel"], r["stage"]): r["n"] for r in ev}
    check("S3 recall_events 落库 arrived+seen 各(API+前端)", ev_map.get(("absence", "arrived")) == 2 and ev_map.get(("absence", "seen")) == 2, str(ev))

    # ---------- S4 静默守披露（cap 补齐口径）----------
    cid_d = make_challenge(token, "r21披露D")
    asyncio.run(seed_day(cid_d, uid, shift(4), 15.0))  # 仅 day1 超限记录，其后静默=守住
    t = api("GET", f"/challenges/{cid_d}/today", token=token)
    t = t.get("data") or t
    check("S4 silent_kept 上桌且>0(断2天补齐守)", int(t.get("silent_kept") or 0) >= 2, f"silent={t.get('silent_kept')} streak={t.get('streak')}")
    j = t.get("journey") or {}
    check("S4 journey guard 补齐口径", int(j.get("guard_days") or 0) >= 3, f"guard={j.get('guard_days')} silent={j.get('guard_silent')}")

    # ---------- 清理 ----------
    asyncio.run(db_cleanup([cid_a, cid_b, cid_c, cid_d]))
    print(f"\n=== {len(passed)} passed, {len(failed)} failed ===")
    for name, detail in failed:
        print(f"  FAIL {name} :: {detail[:140]}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
