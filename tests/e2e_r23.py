"""r23 API E2E：缺席中的毕业——毕业推送缺席变体 + absence gate graduated lane + 凭证链降级保底。

进程内真链（真 ASGI+真临时库+真业务代码，教训#464 配方），触达通道捕获型假 client。
W1 凭证链在本地不可达 Lion/UC 的环境下验证「全源失败→legacy 兜底→guard fail-open」
的降级保底；真链换取 200 的验证在部署后于 edge-04 生产执行。
"""
from __future__ import annotations

import asyncio
import datetime
import os
import sys
import tempfile
import time

sys.path.insert(0, ".")

os.environ.setdefault("UC__JWT_SECRET", "cp-r23-e2e-secret")
os.environ.setdefault("UC__APP_KEY", "cp-r23-e2e")
os.environ.setdefault("UC__APP_SECRET", "cp-r23-e2e-secret")
os.environ.setdefault("LION__BASE_URL", "http://127.0.0.1:1")
os.environ.setdefault("SERVICE_TOKEN", "cp-r23-e2e-service")
os.environ.setdefault("NOTIFY_CENTER_URL", "http://127.0.0.1:1")

_tmpdb = tempfile.mkstemp(suffix=".db")[1]
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///" + _tmpdb

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


class FakeNotify:
    def __init__(self):
        self.sent: list[dict] = []
        self.read_ids: set[int] = set()

    async def send(self, **kwargs):
        self.sent.append(kwargs)
        return {"status": "sent", "id": len(self.sent)}

    async def send_many(self, items):
        out = []
        for item in items:
            out.append(await self.send(**item))
        return out

    async def read_status(self, ids):
        return {int(i): (int(i) in self.read_ids) for i in ids}


async def _setup():
    from app.db.database import init_db, run_migrations

    await init_db()
    await run_migrations()


async def _mk_graduated_challenge(uid, title, last_checkin_days_ago) -> int:
    """阶梯挑战：间隔 2、12→3，无顺延 goal_day=19；start 取 22 天前=已毕业 3 天。"""
    from app.db.database import async_session
    from app.models.challenge import Challenge

    start = datetime.date.today() - datetime.timedelta(days=22)
    end = start + datetime.timedelta(days=60)
    async with async_session() as session:
        ch = Challenge(
            user_id=uid, title=title, category="quit", duration_days=60,
            start_date=start.strftime("%Y-%m-%d"), end_date=end.strftime("%Y-%m-%d"),
            task_type="counter", unit="根", direction="decrease",
            goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
            target_value=15.0, status="active",
            ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
        )
        session.add(ch)
        await session.commit()
        await session.refresh(ch)
        cid = int(ch.id)
    if last_checkin_days_ago is not None:
        await _seed_checkin(cid, uid, shift(last_checkin_days_ago), value=6.0)
    return cid


async def _seed_checkin(challenge_id, user_id, date, value=6.0):
    from app.db.database import async_session
    from app.repositories.challenge_repository import ChallengeRepository
    from app.repositories.checkin_repository import CheckInRepository
    from app.services.goal_rule_service import daily_target
    from app.services.streak_service import day_number_of

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


async def _run_graduation_push(fake: FakeNotify) -> list[dict]:
    from app.db.database import async_session
    from app.services.graduation_service import GraduationPushService

    svc = GraduationPushService()
    from nexus.notify import get_notify_client

    orig = get_notify_client
    import app.services.graduation_service as gs

    gs.get_notify_client = lambda: fake
    try:
        async with async_session() as session:
            from app.repositories.challenge_repository import ChallengeRepository

            challenges = await ChallengeRepository().get_all_active(session)
            items: list[dict] = []
            for c in challenges:
                if str(getattr(c, "direction", "") or "") != "decrease":
                    continue
                items.extend(await svc.scan_challenge(session, c))
            if items:
                await session.commit()
            return items
    finally:
        gs.get_notify_client = orig


async def _get_challenge(cid):
    from app.db.database import async_session
    from app.repositories.challenge_repository import ChallengeRepository

    async with async_session() as session:
        return await ChallengeRepository().get_by_id(session, cid)


async def _collect_absence(challenge, fake: FakeNotify) -> list[dict]:
    from app.db.database import async_session
    from app.services import absence_service

    absence_service.get_notify_client = lambda: fake
    async with async_session() as session:
        return await absence_service.collect_absence_items(session, [challenge])


async def _mark_absence(item, fake: FakeNotify):
    from app.db.database import async_session
    from app.services.absence_service import mark_absence_sent

    rid = (await fake.send_many([item["payload"]]))[0]["id"]
    async with async_session() as session:
        await mark_absence_sent(
            session, challenge_id=item["challenge_id"], user_id=item["user_id"],
            absence=item["absence"], gate=item["gate"], notif_id=rid,
        )
        await session.commit()
    return rid


async def _backdate_absence_touch(challenge_id, days_ago):
    from sqlalchemy import update
    from app.core.datetime_utils import now_china
    from app.db.database import async_session
    from app.models.checkin import AIInsight
    from app.models.reminder import TouchState

    old = shift(days_ago)
    async with async_session() as session:
        await session.execute(
            update(TouchState)
            .where(TouchState.challenge_id == challenge_id, TouchState.kind == "absence")
            .values(last_sent_at=now_china() - datetime.timedelta(days=days_ago))
        )
        await session.execute(
            update(AIInsight)
            .where(AIInsight.challenge_id == challenge_id,
                   AIInsight.insight_type == "absence_care")
            .values(content='{"date": "' + old + '"}')
        )
        await session.commit()


async def main():
    await _setup()

    # ---------- G1/G2 毕业推送双变体 ----------
    print("[G] 毕业推送：在场庆祝 vs 缺席诚实")
    uid_a, uid_b = f"ga{int(time.time())}", f"gb{int(time.time())}"
    cid_present = await _mk_graduated_challenge(uid_a, "在场毕业", last_checkin_days_ago=1)
    cid_absent = await _mk_graduated_challenge(uid_b, "缺席毕业", last_checkin_days_ago=14)

    fake1 = FakeNotify()
    items = await _run_graduation_push(fake1)
    by_c = {}
    for it in items:
        by_c[it["data"]["challenge_id"]] = it
    p, a = by_c.get(cid_present), by_c.get(cid_absent)
    check("G1a 在场毕业=庆祝变体带降幅", bool(p) and "阶梯毕业" in p["title"] and "%" in p["content"], str(p and p["title"]))
    check("G1b 在场毕业文案含证书行动号召", bool(p) and "毕业证书已生成" in p["content"], str(p and p["content"]))
    check("G2a 缺席毕业=诚实变体", bool(a) and "阶梯走完了" in a["title"], str(a and a["title"]))
    check("G2b 缺席毕业无降幅冒领", bool(a) and "%)" not in a["content"], str(a and a["content"]))
    check("G2c 缺席毕业保留证书承诺", bool(a) and "不会过期" in a["content"], str(a and a["content"]))

    fake1b = FakeNotify()
    items_again = await _run_graduation_push(fake1b)
    check("G2d 毕业推送 insight 去重不重发", len(items_again) == 0, str([i["title"] for i in items_again]))

    # ---------- G3 absence gate graduated lane ----------
    print("[G3] 毕业后缺席：触达从催打卡换证书邀请")
    ch_absent = await _get_challenge(cid_absent)
    fake2 = FakeNotify()
    got = await _collect_absence(ch_absent, fake2)
    check("G3a 毕业后首触=证书在等你", len(got) == 1 and "毕业" in got[0]["payload"]["title"] and "证书" in got[0]["payload"]["title"], str([g["payload"]["title"] for g in got]))
    check("G3b 首触文案不再催打卡上限", bool(got) and "今天上限" not in got[0]["payload"]["content"], str(got and got[0]["payload"]["content"]))
    rid = await _mark_absence(got[0], fake2) if got else 0
    check("G3c TouchState 落痕带 notif_id", rid > 0, str(rid))

    await _backdate_absence_touch(cid_absent, days_ago=8)
    fake3 = FakeNotify()
    got2 = await _collect_absence(ch_absent, fake3)
    check("G3d 8天后 REVIVE=door 证书邀请", len(got2) == 1 and got2[0]["gate"]["action"] == "revive" and "毕业证书在等你" in got2[0]["payload"]["title"], str([g["payload"]["title"] for g in got2]))
    rid2 = await _mark_absence(got2[0], fake3) if got2 else 0

    await _backdate_absence_touch(cid_absent, days_ago=8)
    fake4 = FakeNotify()
    fake4.read_ids.add(rid2)  # 已读未行动 → switch 换道
    import nexus.notify as nexus_notify_mod

    _orig_gnc = nexus_notify_mod.get_notify_client
    nexus_notify_mod.get_notify_client = lambda: fake4
    try:
        got3 = await _collect_absence(ch_absent, fake4)
    finally:
        nexus_notify_mod.get_notify_client = _orig_gnc
    check("G3e 已读未行动=switch 安静出口", len(got3) == 1 and got3[0]["gate"]["lane"] == "switch" and "不会过期" in got3[0]["payload"]["title"], str([g["payload"]["title"] for g in got3]))

    # ---------- G4 凭证链降级保底（Lion/UC 不可达） ----------
    print("[G4] 凭证链全源失败→legacy 兜底→guard fail-open 保底")
    uid_c = f"gc{int(time.time())}"
    from app.db.database import async_session
    from app.models.challenge import Challenge

    start = datetime.date.today() - datetime.timedelta(days=3)
    async with async_session() as session:
        session.add(Challenge(
            user_id=uid_c, title="英语打卡", category="learn", duration_days=30,
            start_date=start.strftime("%Y-%m-%d"),
            end_date=(start + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
            task_type="word", unit="词", direction="increase", goal_type="hard",
            goal_rule="fixed", goal_mode="floor", target_value=20.0, status="active",
        ))
        await session.commit()
    os.environ.pop("REMINDER_GUARD_OFF", None)
    from app.services import reminder_service

    fake5 = FakeNotify()
    reminder_service.get_notify_client = lambda: fake5
    await reminder_service.send_checkin_reminders(current_hour=20)
    check("G4a guard fail-open 下提醒照发", len(fake5.sent) >= 1, str([s.get("title") for s in fake5.sent]))
    os.environ["REMINDER_GUARD_OFF"] = "1"

    print(f"\n===== r23 E2E: {len(passed)} passed / {len(failed)} failed =====")
    for name, detail in failed:
        print(f"  FAILED: {name} :: {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
