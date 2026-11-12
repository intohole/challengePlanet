"""r27 回流重启引擎 E2E：ASGITransport 真路由全链（回归→建议→接受重锚→上限生效→拒绝保持）。

鉴权走 dependency_overrides（本地无 UC）；临时库隔离；不触 lifespan。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SERVICE_TOKEN", "e2e-r27-svc")

import app.models  # noqa: F401 register all tables
from app.core.datetime_utils import now_china
from app.db.database import Base, get_db
from app.main import app
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.streak_service import shift_date, today_str
from nexus import get_current_user_id_required

E2E_UID = "e2e_r27_user"
API = "/api/v1/challenges"

passed: list[str] = []
failed: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" :: " + extra if extra and not cond else ""))


async def _seed_gap_challenge(SM, uid: str) -> int:
    today = today_str()
    async with SM() as s:
        ch = Challenge(
            user_id=uid, title="戒断挑战", category="quit", task_type="counter", unit="根",
            direction="decrease", goal_type="soft", goal_rule="ladder", goal_mode="ceiling",
            duration_days=66, status="active",
            ladder_start=12.0, ladder_goal=3.0, ladder_interval=2, ladder_step=1.0,
            ladder_adjust=json.dumps([{"day": 6, "shift": 2}]),
            target_value=12.0, ai_plan="[]", share_token="t r27", color="#ef4444", icon="🚭",
            start_date=shift_date(today, -34), end_date=shift_date(today, 31),
        )
        s.add(ch)
        await s.flush()
        gap_start = shift_date(today, -27)
        for d, v in [(shift_date(gap_start, -2), 2.0), (gap_start, 5.0), (gap_start, 2.0)]:
            s.add(CheckIn(
                challenge_id=ch.id, user_id=uid, date=d, value=v, day_number=1,
                status="done", target_value=12.0, timestamp=now_china(),
                unit="根", direction="decrease",
            ))
        await s.commit()
        return int(ch.id)


async def main() -> int:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_async_engine("sqlite+aiosqlite:///" + db_path)
    SM = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ch_id = await _seed_gap_challenge(SM, E2E_UID)
    ch2_id = await _seed_gap_challenge(SM, E2E_UID)

    async def override_user() -> str:
        return E2E_UID

    async def override_db():
        async with SM() as s:
            yield s

    app.dependency_overrides[get_current_user_id_required] = override_user
    app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer e2e-r27-svc"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(f"{API}/{ch_id}/today", headers=headers)
        check("today 200", r.status_code == 200, r.text[:200])
        t = r.json()
        rs = t.get("return_state") or {}
        check("回归态触发（gap≥2 真实记录口径）", int(rs.get("gap_days") or 0) >= 2, str(rs.get("gap_days")))
        rst = rs.get("restart") or {}
        check("重启建议随回归态出口", rst.get("status") == "pending", str(rst)[:120])
        check("建议量=缺口前守住量 7", float(rst.get("restart_cap") or 0) == 7.0, str(rst.get("restart_cap")))
        check("当前日历 cap=3", float(rst.get("current_cap") or 0) == 3.0, str(rst.get("current_cap")))
        check("重锚前今日上限=3", float(t.get("today_target") or 0) == 3.0, str(t.get("today_target")))
        sid = int(rst.get("suggestion_id") or 0)

        r = await client.get(f"{API}/{ch_id}/adaptive/pending", headers=headers)
        pend = (r.json() or {}).get("suggestion") or {}
        check("pending 端点出 restart 建议", pend.get("kind") == "restart", str(pend.get("kind")))

        r = await client.get(f"{API}/{ch_id}/today", headers=headers)
        rst2 = ((r.json().get("return_state") or {}).get("restart") or {})
        check("重复打开幂等（同建议不重建）", int(rst2.get("suggestion_id") or 0) == sid, str(rst2.get("suggestion_id")))

        r = await client.post(f"{API}/{ch_id}/adaptive/{sid}/respond", headers=headers,
                              json={"accept": True})
        check("接受重启 200", r.status_code == 200, r.text[:200])
        check("applied=true", (r.json() or {}).get("applied") is True, r.text[:200])

        r = await client.get(f"{API}/{ch_id}/today", headers=headers)
        t = r.json()
        check("重锚后今日上限=7", float(t.get("today_target") or 0) == 7.0, str(t.get("today_target")))
        rst3 = ((t.get("return_state") or {}).get("restart") or {})
        check("接受后重启卡退场", not rst3, str(rst3)[:80])

        r = await client.get(f"{API}/{ch2_id}/today", headers=headers)
        t2 = r.json()
        rst_b = ((t2.get("return_state") or {}).get("restart") or {})
        check("第二挑战建议在场", rst_b.get("status") == "pending", str(rst_b)[:80])
        sid_b = int(rst_b.get("suggestion_id") or 0)
        r = await client.post(f"{API}/{ch2_id}/adaptive/{sid_b}/respond", headers=headers,
                              json={"accept": False})
        check("拒绝 200", r.status_code == 200, r.text[:200])
        r = await client.get(f"{API}/{ch2_id}/today", headers=headers)
        t2 = r.json()
        check("拒绝后上限保持日历 3", float(t2.get("today_target") or 0) == 3.0, str(t2.get("today_target")))
        check("拒绝后重启卡退场", not ((t2.get("return_state") or {}).get("restart") or {}), "")

    app.dependency_overrides.clear()
    print(f"\n== r27 restart E2E: {len(passed)} passed / {len(failed)} failed ==")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
