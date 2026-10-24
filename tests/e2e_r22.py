"""r22 API E2E：触达语义 gate（首触/静默/REVIVE/SUNSET）+ 双丢失修复 + 回归页/回填。

进程内真链（真 ASGI+真临时库+真业务代码），认证用同钥铸造 HS256（教训#464 配方：
被测对象不是认证时别让认证挡路），触达通道用捕获型假 client（工作区既定形态）。
"""
from __future__ import annotations

import asyncio
import datetime
import json
import os
import sys
import tempfile
import time
from types import SimpleNamespace

sys.path.insert(0, ".")

os.environ.setdefault("UC__JWT_SECRET", "cp-r22-e2e-secret")
os.environ.setdefault("UC__APP_KEY", "cp-r22-e2e")
os.environ.setdefault("UC__APP_SECRET", "cp-r22-e2e-secret")
os.environ.setdefault("REMINDER_GUARD_OFF", "1")
os.environ.setdefault("LION__BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("SERVICE_TOKEN", "cp-r22-e2e-service")
os.environ.setdefault("NOTIFY_CENTER_URL", "http://127.0.0.1:1")

_tmpdb = tempfile.mkstemp(suffix=".db")[1]
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb

import jwt  # noqa: E402

SECRET = os.environ["UC__JWT_SECRET"]
STAMP = str(int(time.time()))[-6:]

passed: list[str] = []
failed: list[tuple[str, str]] = []


def check(name, cond, detail=""):
    if cond:
        passed.append(name)
        print(f"  PASS {name}")
    else:
        failed.append((name, detail))
        print(f"  FAIL {name} :: {detail}")


def shift(days_ago):
    return (datetime.date.today() - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


def mint(uid: str) -> str:
    return jwt.encode({"sub": uid, "exp": int(time.time()) + 3600}, SECRET, algorithm="HS256")


class FakeNotify:
    def __init__(self, fail_rescue=False):
        self.sent: list[dict] = []
        self.fail_rescue = fail_rescue

    async def send(self, **kwargs):
        if self.fail_rescue and (kwargs.get("data") or {}).get("rescue"):
            return {"status": "failed", "id": 0, "reason": "e2e_injected"}
        self.sent.append(kwargs)
        return {"status": "sent", "id": len(self.sent)}

    async def send_many(self, items):
        out = []
        for item in items:
            out.append(await self.send(**item))
        return out


async def _setup():
    from app.db.database import init_db, run_migrations

    await init_db()
    await run_migrations()


async def _seed_checkin(challenge_id, user_id, date, value=5.0):
    from app.repositories.challenge_repository import ChallengeRepository
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.goal_rule_service import daily_target
    from app.services.streak_service import day_number_of
    from app.db.database import async_session

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


async def _mk_challenge(uid, title, *, cap=True, start_days_ago=6) -> int:
    from app.models.challenge import Challenge
    from app.db.database import async_session

    end = (datetime.date.today() - datetime.timedelta(days=start_days_ago)
           + datetime.timedelta(days=60)).strftime("%Y-%m-%d")
    body = dict(
        user_id=uid, title=title, category="quit" if cap else "learn",
        duration_days=60, start_date=shift(start_days_ago), end_date=end,
        task_type="counter", unit="个" if not cap else "根",
        direction="decrease" if cap else "increase",
        goal_type="soft" if cap else "hard",
        goal_rule="ladder" if cap else "fixed", goal_mode="ceiling" if cap else "floor",
        target_value=15.0 if cap else 20.0, status="active",
    )
    if cap:
        body.update(ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0)
    async with async_session() as session:
        ch = Challenge(**body)
        session.add(ch)
        await session.commit()
        await session.refresh(ch)
        return int(ch.id)


async def _run_job(fake: FakeNotify):
    from app.services import reminder_service

    reminder_service.get_notify_client = lambda: fake
    await reminder_service.send_checkin_reminders(current_hour=20)


async def _touch_states(challenge_id=None):
    from sqlalchemy import select
    from app.models.reminder import TouchState
    from app.db.database import async_session

    async with async_session() as session:
        q = select(TouchState)
        if challenge_id:
            q = q.where(TouchState.challenge_id == challenge_id)
        return list((await session.execute(q)).scalars().all())


async def _set_touch_sent(challenge_id, kind, days_ago):
    from sqlalchemy import update
    from app.models.reminder import TouchState
    from app.models.checkin import AIInsight
    from app.core.datetime_utils import now_china
    from app.db.database import async_session

    old = shift(days_ago)
    async with async_session() as session:
        await session.execute(
            update(TouchState)
            .where(TouchState.challenge_id == challenge_id, TouchState.kind == kind)
            .values(last_sent_at=now_china() - datetime.timedelta(days=days_ago))
        )
        await session.execute(
            update(AIInsight)
            .where(AIInsight.challenge_id == challenge_id,
                   AIInsight.insight_type.in_(["absence_care", "rescue_care"]))
            .values(content='{"date": "' + old + '"}')
        )
        await session.commit()


async def _today_task(token, cid):
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.get(
            f"/api/v1/challenges/{cid}/today",
            headers={"Authorization": "Bearer " + token},
        )
        return r.status_code, (r.json() if r.status_code == 200 else r.text)


async def _checkin(token, cid, value=1.0):
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post(
            f"/api/v1/challenges/{cid}/checkin",
            headers={"Authorization": "Bearer " + token},
            json={"value": value},
        )
        return r.status_code, (r.json() if r.status_code == 200 else r.text)


async def _meta_extra(cid):
    from nexus import loads_or
    from app.models.points import ChallengeMeta
    from app.db.database import async_session

    async with async_session() as session:
        meta = await session.get(ChallengeMeta, cid)
        return loads_or(str(meta.extra or "{}"), {}) if meta else {}


async def _cleanup(cids):
    from sqlalchemy import delete
    from app.models.checkin import AIInsight, CheckIn
    from app.models.challenge import Challenge
    from app.models.points import ChallengeMeta
    from app.models.reminder import TouchState
    from app.db.database import async_session

    async with async_session() as session:
        if cids:
            for tbl in (CheckIn, AIInsight, ChallengeMeta, TouchState):
                await session.execute(delete(tbl).where(tbl.challenge_id.in_(cids)))
            await session.execute(delete(Challenge).where(Challenge.id.in_(cids)))
        await session.commit()


def main():
    asyncio.run(_setup())
    uid = "r22e2e_" + STAMP
    token = mint(uid)
    cids: list[int] = []

    try:
        # ---------- E1 回归页：缺席 2 天后打开 app（未打卡）→ today-task 带回归态 ----------
        async def e1():
            cid = await _mk_challenge(uid, "r22回归A", cap=False, start_days_ago=6)
            cids.append(cid)
            await _seed_checkin(cid, uid, shift(4))
            return cid

        cid_a = asyncio.run(e1())
        code, t = asyncio.run(_today_task(token, cid_a))
        rs = (t or {}).get("return_state") if isinstance(t, dict) else None
        check("E1a 缺席3天打开app出回归态", code == 200 and rs is not None, f"{code} {rs}")
        ok = rs and rs["gap_days"] == 3 and rs["return_day"] == 1 and rs["micro_target"] == 4
        check("E1b 回归态字段(离开3天/第1天/最小动作)", bool(ok), str(rs))

        # ---------- E2 回来第 3 天回赠免费补签卡 ----------
        async def e2():
            cid = await _mk_challenge(uid, "r22回归B", cap=False, start_days_ago=8)
            cids.append(cid)
            await _seed_checkin(cid, uid, shift(5))
            await _seed_checkin(cid, uid, shift(2))
            await _seed_checkin(cid, uid, shift(1))
            return cid

        cid_b = asyncio.run(e2())
        code, res = asyncio.run(_checkin(token, cid_b))
        rs2 = (res or {}).get("return_state") if isinstance(res, dict) else None
        check("E2a 第3天打卡回赠标记", code == 200 and rs2 and rs2.get("reward_granted") is True, f"{code} {rs2}")
        extra = asyncio.run(_meta_extra(cid_b))
        check("E2b bonus_mends 落账+episode 锚", extra.get("bonus_mends") == 1 and extra.get("backfill_episode"), str(extra))

        # ---------- E3 absence gate：首触落状态+同日重跑静默 ----------
        async def e3():
            cid = await _mk_challenge(uid, "r22缺席C", cap=True, start_days_ago=6)
            cids.append(cid)
            await _seed_checkin(cid, uid, shift(3), value=5.0)
            return cid

        cid_c = asyncio.run(e3())
        fake = FakeNotify()
        asyncio.run(_run_job(fake))
        cares = [s for s in fake.sent if (s.get("data") or {}).get("absence_care")]
        check("E3a 缺席期首触 care 发出", len(cares) == 1, str([s.get("title") for s in fake.sent]))
        states = asyncio.run(_touch_states(cid_c))
        check("E3b TouchState 落痕带 notif_id", len(states) == 1 and states[0].last_notif_id > 0, str(states))
        fake2 = FakeNotify()
        asyncio.run(_run_job(fake2))
        c_again = [s for s in fake2.sent if f"ch={cid_c}" in str(s.get("link", ""))]
        check("E3c 同日重跑静默", len(c_again) == 0, str([s.get("title") for s in fake2.sent]))

        # ---------- E4 REVIVE：同 episode ≥7 天 → 门开着变体 + rc=revive ----------
        asyncio.run(_set_touch_sent(cid_c, "absence", 8))
        fake3 = FakeNotify()
        asyncio.run(_run_job(fake3))
        revives = [s for s in fake3.sent if (s.get("data") or {}).get("touch_action") == "revive"]
        check("E4a 7天后REVIVE变体", len(revives) == 1 and "门一直开着" in str(revives[0].get("title", "")), str([s.get("title") for s in fake3.sent]))
        check("E4b REVIVE 深链 rc=revive", bool(revives) and "rc=revive" in str(revives[0].get("link", "")), str(revives[0].get("link") if revives else None))

        # ---------- E5 SUNSET：缺席超 30 天诚实退场 ----------
        async def e5():
            cid = await _mk_challenge(uid, "r22退场D", cap=True, start_days_ago=45)
            cids.append(cid)
            await _seed_checkin(cid, uid, shift(40), value=5.0)
            return cid

        cid_d = asyncio.run(e5())
        fake4 = FakeNotify()
        asyncio.run(_run_job(fake4))
        mine = [s for s in fake4.sent if str(s.get("user_id")) == uid and (s.get("data") or {}).get("absence_care")]
        check("E5 缺席>30天SUNSET零触达", len(mine) == 0, str([s.get("title") for s in mine]))

        # ---------- E6 双丢失修复：rescue 发送失败 → normal 提醒兜底 ----------
        async def e6():
            cid = await _mk_challenge(uid, "r22丢失E", cap=False, start_days_ago=6)
            cids.append(cid)
            await _seed_checkin(cid, uid, shift(4))
            return cid

        cid_e = asyncio.run(e6())
        fake5 = FakeNotify(fail_rescue=True)
        asyncio.run(_run_job(fake5))
        mine5 = [s for s in fake5.sent if str(s.get("user_id")) == uid]
        has_rescue = any((s.get("data") or {}).get("rescue") for s in mine5)
        has_normal = any("打卡提醒" in str(s.get("title", "")) or "待打卡" in str(s.get("title", "")) for s in mine5)
        check("E6a rescue失败不送达", has_rescue is False, str([s.get("title") for s in mine5]))
        check("E6b normal提醒兜底当日不空窗", has_normal is True, str([s.get("title") for s in mine5]))

        # ---------- E7 rescue 成功 → 同用户 normal 抑制 ----------
        fake6 = FakeNotify()
        asyncio.run(_run_job(fake6))
        mine6 = [s for s in fake6.sent if str(s.get("user_id")) == uid]
        rescues6 = [s for s in mine6 if (s.get("data") or {}).get("rescue")]
        normals6 = [s for s in mine6 if "打卡提醒" in str(s.get("title", ""))]
        check("E7 rescue成功则normal抑制", len(rescues6) == 1 and len(normals6) == 0, str([s.get("title") for s in mine6]))

        # ---------- E8 每用户每日聚合频控 ≤3 ----------
        async def e8():
            out = []
            for i in range(4):
                cid = await _mk_challenge(uid, f"r22频控{i}", cap=False, start_days_ago=6)
                cids.append(cid)
                await _seed_checkin(cid, uid, shift(4))
                out.append(cid)
            return out

        asyncio.run(e8())
        fake7 = FakeNotify()
        asyncio.run(_run_job(fake7))
        mine7 = [s for s in fake7.sent if str(s.get("user_id")) == uid]
        check("E8 单用户单日聚合≤3", len(mine7) <= 3, f"{len(mine7)} sent")

        # ---------- E9 funnel 回归（r21 资产不受本轮破坏）----------
        async def e9():
            from app.services.recall_service import build_funnel, track_event
            from app.db.database import async_session

            async with async_session() as session:
                await track_event(session, uid, cid_a, "absence", "arrived", notif_id="1")
                await session.commit()
            async with async_session() as session:
                return await build_funnel(session, days=7, user_id=uid)

        funnel = asyncio.run(e9())
        totals = funnel.get("event_totals") or {}
        check("E9 漏斗 arrived 事件落库", isinstance(totals, dict) and totals.get("absence:arrived", 0) >= 1, str(funnel)[:200])

    finally:
        asyncio.run(_cleanup(cids))

    print(f"\n=== e2e_r22: {len(passed)} passed, {len(failed)} failed ===")
    if failed:
        for name, detail in failed:
            print(f"  FAIL {name} :: {detail}")
        sys.exit(1)


if __name__ == "__main__":
    main()
