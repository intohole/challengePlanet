"""r26 SUNSET 诚实终局 E2E：ASGITransport 真路由全链（列表惰性迁移+revive 端点+409 幂等防御）。

鉴权走 dependency_overrides（本地无 UC；端点逻辑=本轮改动面，生产真链断言留部署后终验）。
临时库隔离；不触 lifespan（无 scheduler/ironman 副作用）。
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SERVICE_TOKEN", "e2e-r26-svc")  # nexus 中间件非公开请求门（import app.main 前生效）

import app.models  # noqa: F401 register all tables
from app.core.datetime_utils import now_china
from app.db.database import Base, get_db
from app.main import app
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.streak_service import shift_date, today_str
from nexus import get_current_user_id_required

E2E_UID = "e2e_r26_user"
API = "/api/v1/challenges"

passed: list[str] = []
failed: list[str] = []


def check(name: str, cond: bool, extra: str = "") -> None:
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (" :: " + extra if extra and not cond else ""))


async def main() -> int:
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_async_engine("sqlite+aiosqlite:///" + db_path)
    SM = async_sessionmaker(eng, class_=AsyncSession, expire_on_commit=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    today = today_str()
    async with SM() as s:
        zomb = Challenge(user_id=E2E_UID, title="英语挑战", category="learn", duration_days=66,
                         start_date="2026-09-09", end_date="2026-11-13", status="active",
                         task_type="binary", target_value=1.0, unit="次")
        fresh = Challenge(user_id=E2E_UID, title="新挑战", category="build", duration_days=21,
                          start_date=today, end_date=shift_date(today, 20), status="active",
                          task_type="binary", target_value=1.0, unit="次")
        never = Challenge(user_id=E2E_UID, title="从未启程", category="build", duration_days=66,
                          start_date="2026-09-09", end_date="2026-11-13", status="active",
                          task_type="binary", target_value=1.0, unit="次")
        s.add_all([zomb, fresh, never])
        await s.flush()
        s.add(CheckIn(challenge_id=zomb.id, user_id=E2E_UID, day_number=1, status="kept",
                      timestamp=now_china(), date="2026-10-04", value=1.0, unit="次",
                      target_value=1.0, goal_type="hard", direction="increase"))
        s.add(CheckIn(challenge_id=fresh.id, user_id=E2E_UID, day_number=1, status="kept",
                      timestamp=now_china(), date=today, value=1.0, unit="次",
                      target_value=1.0, goal_type="hard", direction="increase"))
        await s.commit()
        zomb_id, fresh_id, never_id = zomb.id, fresh.id, never.id

    async def override_user() -> str:
        return E2E_UID

    async def override_db():
        async with SM() as s:
            yield s

    app.dependency_overrides[get_current_user_id_required] = override_user
    app.dependency_overrides[get_db] = override_db

    transport = httpx.ASGITransport(app=app)
    headers = {"Authorization": "Bearer e2e-r26-svc"}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(API, headers=headers)
        check("列表 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        items = {c["id"]: c for c in r.json()}
        check("列表惰性迁移：失踪 36 天 → resting", items.get(zomb_id, {}).get("status") == "resting",
              str(items.get(zomb_id, {}).get("status")))
        check("近期活跃不动", items.get(fresh_id, {}).get("status") == "active")
        check("从未启程不判失踪", items.get(never_id, {}).get("status") == "active")
        check("resting 挑战仍在列表（呈现数据在场）", zomb_id in items)

        r = await client.post(f"{API}/{zomb_id}/revive", headers=headers)
        check("revive 200", r.status_code == 200, f"status={r.status_code} body={r.text[:200]}")
        d = r.json()
        check("revive 返回新起期", d.get("revived") is True and d.get("start_date") == today_str(), str(d))

        r = await client.get(API, headers=headers)
        items = {c["id"]: c for c in r.json()}
        check("复活后 active 且计划重开", items.get(zomb_id, {}).get("status") == "active"
              and items.get(zomb_id, {}).get("start_date") == today_str(),
              str(items.get(zomb_id, {}).get("start_date")))

        r = await client.post(f"{API}/{zomb_id}/revive", headers=headers)
        check("active 再复活 409", r.status_code == 409, f"status={r.status_code}")

        r = await client.post(f"{API}/{fresh_id}/revive", headers=headers)
        check("非 resting 形态 409 拒绝", r.status_code == 409, f"status={r.status_code}")

        r = await client.get(API, headers=headers)
        items2 = {c["id"]: c for c in r.json()}
        check("幂等：再次列表形态稳定", items2.get(zomb_id, {}).get("status") == "active"
              and items2.get(never_id, {}).get("status") == "active")

    await eng.dispose()
    print(f"\n{len(passed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
