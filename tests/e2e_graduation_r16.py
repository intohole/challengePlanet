from __future__ import annotations

import asyncio
import datetime
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path
from nexus.utils.time import TimeUtils

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610/api/v1")
ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "challenge.db"

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")


def call(method: str, path: str, payload: dict | None = None, token: str = "") -> tuple[int, dict | list]:
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        method=method,
        headers={
            "Content-Type": "application/json",
            **({"Authorization": "Bearer " + token} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def shift(day: str, n: int) -> str:
    d = datetime.datetime.strptime(day, "%Y-%m-%d") + datetime.timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def insert_checkin(conn, ch_id, user_id, day, value, unit, target):
    conn.execute(
        "INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit, target_value, goal_type, direction) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ch_id, user_id, day + " 10:00:00", 1, day, "completed", "", "", "", "", 100.0, value, unit, target, "soft", "decrease"),
    )


def run_scan(ch_id: int) -> list[dict]:
    from app.db.database import async_session, init_db
    from app.repositories.challenge_repository import ChallengeRepository
    from app.services.graduation_service import GraduationPushService

    async def _run():
        await init_db()
        async with async_session() as session:
            ch = await ChallengeRepository().get_by_id(session, ch_id)
            if ch is None:
                return []
            return await GraduationPushService().scan_challenge(session, ch)

    return asyncio.run(_run())


def run_close() -> int:
    from app.db.database import async_session, init_db
    from app.services.challenge_service import ChallengeService

    async def _run():
        await init_db()
        async with async_session() as session:
            return await ChallengeService().close_finished(session)

    return asyncio.run(_run())


def main() -> int:
    today = TimeUtils.now_naive().strftime("%Y-%m-%d")
    name = f"r16grad{int(time.time())%1000000}"

    print("== 1. 注册 + 建已到终点的阶梯挑战（25→1，26 天前开始，day27 >= goal_day25） ==")
    status, body = call("POST", "/auth/register", {"username": name, "password": "R16Grad#2026", "nickname": name})
    data = body.get("data", body) if isinstance(body, dict) else {}
    token = data.get("access_token") or data.get("token") or ""
    check("注册", status == 200 and token, f"{status}")
    user_id = data.get("user", {}).get("id") or data.get("user_id") or ""
    if not user_id:
        status, body = call("GET", "/auth/me", token=token)
        user_id = (body.get("data", body) or {}).get("id", "")

    status, body = call("POST", "/challenges/confirm", {
        "title": "e2e毕业", "description": "阶梯走完", "category": "quit",
        "duration_days": 32, "start_date": shift(today, -26), "source": "manual",
        "task_type": "counter", "scene_template": "quit", "target_value": 25, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "ladder_start": 25, "ladder_goal": 1, "ladder_interval": 1, "ladder_step": 1,
        "plan": [],
    }, token)
    check("创建挑战", status == 200, f"{status} {body}")
    ch_id = (body.get("data", body) or {}).get("id")

    print("== 2. 直插历史（4/4 根两天）+ 今天 0 根 HTTP 记录 ==")
    conn = sqlite3.connect(DB_PATH)
    insert_checkin(conn, ch_id, user_id, shift(today, -3), 4, "根", 23.0)
    insert_checkin(conn, ch_id, user_id, shift(today, -2), 4, "根", 24.0)
    conn.commit()
    conn.close()

    status, body = call("POST", f"/challenges/{ch_id}/checkin", {"value": 0, "mood": "good"}, token)
    check("今天 0 根打卡 200", status == 200, f"{status} {str(body)[:120]}")
    status, body = call("GET", f"/challenges/{ch_id}/today", token=token)
    t = body.get("data", body) if isinstance(body, dict) else {}
    check("today_total=0", float(t.get("today_total") or 0) == 0.0, str(t.get("today_total")))
    check("零根日有记录", len(t.get("today_checkins") or []) == 1, str(len(t.get("today_checkins") or [])))

    print("== 3. journey.graduation 毕业态 + 健康线锚定切换 ==")
    j = t.get("journey") or {}
    g = j.get("graduation") or {}
    check("graduation 存在", bool(g), str(j)[:100])
    check("state=graduated", g.get("state") == "graduated", str(g.get("state")))
    check("毕业日=开始+24", g.get("graduation_date") == shift(today, -2), str(g.get("graduation_date")))
    check("keep_day>=2", int(g.get("keep_day") or 0) >= 2, str(g.get("keep_day")))
    check("final_cap=1", float(g.get("final_cap") or 0) == 1.0, str(g.get("final_cap")))
    health = j.get("health") or {}
    check("健康线锚定毕业日", health.get("anchor_date") == shift(today, -2), str(health.get("anchor_date")))
    check("锚定文案=毕业那天起", health.get("anchor_label") == "从你阶梯毕业那天起", str(health.get("anchor_label")))
    reached = [m["key"] for m in health.get("milestones", []) if m["reached"]]
    check("毕业 2 天已达成 hr/co", set(reached) == {"hr_20min", "co_12h"}, str(reached))
    check("少抽=42+25=67", j.get("cigarettes_avoided") == 21 + 21 + 25, str(j.get("cigarettes_avoided")))

    print("== 4. 推送扫描：里程碑+毕业各一次，幂等 ==")
    items = run_scan(ch_id)
    titles = [str(i.get("title", "")) for i in items]
    check("毕业推送生成", any("阶梯毕业" in x for x in titles), str(titles))
    check("里程碑推送生成", any("少抽" in x for x in titles), str(titles))
    items2 = run_scan(ch_id)
    check("二次扫描幂等零新增", len(items2) == 0, str([i.get('title') for i in items2]))
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT content FROM ai_insights WHERE challenge_id=? AND insight_type='journey_push' ORDER BY id DESC LIMIT 1",
        (ch_id,),
    ).fetchone()
    conn.close()
    payload = json.loads(row[0]) if row else {}
    check("去重状态落库", "graduated" in payload and "avoided_50" in payload, str(payload))

    print("== 5. close_finished 毕业语义 ==")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE challenges SET end_date=? WHERE id=?", (shift(today, -1), ch_id))
    conn.commit()
    conn.close()
    closed = run_close()
    check("归档 1 条", closed >= 1, str(closed))
    conn = sqlite3.connect(DB_PATH)
    st = conn.execute("SELECT status FROM challenges WHERE id=?", (ch_id,)).fetchone()
    conn.close()
    check("status=graduated", st and st[0] == "graduated", str(st))

    print("== 6. 深链与 cron 可观测 ==")
    status, body = call("GET", "/tools/cron-status", token=token)
    cs = body.get("data", body) if isinstance(body, dict) else {}
    check("cron-status alive", cs.get("alive") is True, str(cs)[:100])
    nxt = cs.get("jobs_next_run_at") or {}
    check("4 job next_run_at", len(nxt) == 4, str(nxt))
    req = urllib.request.Request("http://127.0.0.1:8610/health")
    with urllib.request.urlopen(req) as resp:
        h = json.loads(resp.read().decode())
    check("health cron_next_run_at", bool(h.get("cron_next_run_at")), str(h.get("cron_next_run_at"))[:80])
    req = urllib.request.Request("http://127.0.0.1:8610/static/js/graduation-cert.js")
    try:
        with urllib.request.urlopen(req) as resp:
            check("graduation-cert.js 可达", resp.status == 200, str(resp.status))
    except urllib.error.HTTPError as e:
        check("graduation-cert.js 可达", False, str(e.code))
    req = urllib.request.Request("http://127.0.0.1:8610/")
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
    check("首页引用 graduation-cert", "graduation-cert.js" in html, "")
    check("首页引用新指纹", "home-task.js?v=20261005a" in html, "")

    print("== 7. 清理 ==")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM checkins WHERE challenge_id=?", (ch_id,))
    conn.execute("DELETE FROM ai_insights WHERE challenge_id=?", (ch_id,))
    conn.execute("DELETE FROM challenges WHERE id=?", (ch_id,))
    if user_id:
        for table in ("points_ledger", "streak_actions", "chat_messages", "chat_conversations"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE user_id=?", (str(user_id),))
            except sqlite3.OperationalError:
                pass
    conn.commit()
    conn.close()
    check("清理完成", True)

    print(f"\n== 结果: {PASS} passed / {FAIL} failed ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
