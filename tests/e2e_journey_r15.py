from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610/api/v1")
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "challenge.db"

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


def main() -> int:
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    name = f"r15quit{int(time.time())%1000000}"

    print("== 1. 注册 + 建戒烟阶梯挑战（25→1，19 天前开始） ==")
    status, body = call("POST", "/auth/register", {"username": name, "password": "R15Quit#2026", "nickname": name})
    data = body.get("data", body) if isinstance(body, dict) else {}
    token = data.get("access_token") or data.get("token") or ""
    check("注册", status == 200 and token, f"{status}")
    user_id = data.get("user", {}).get("id") or data.get("user_id") or ""

    status, body = call("POST", "/challenges/confirm", {
        "title": "e2e戒烟", "description": "从每天25根减下来", "category": "quit",
        "duration_days": 30, "start_date": shift(today, -18), "source": "manual",
        "task_type": "counter", "scene_template": "quit", "target_value": 25, "unit": "根",
        "direction": "decrease", "goal_type": "soft", "goal_rule": "ladder",
        "ladder_start": 25, "ladder_goal": 1, "ladder_interval": 1, "ladder_step": 1,
        "plan": [],
    }, token)
    check("创建戒烟挑战", status == 200, f"{status} {body}")
    data = body.get("data", body) if isinstance(body, dict) else {}
    ch_id = data.get("id")
    if not user_id:
        status, body = call("GET", "/auth/me", token=token)
        user_id = (body.get("data", body) or {}).get("id", "")

    print("== 2. 直插 3 天历史（3/11/4 根） ==")
    conn = sqlite3.connect(DB_PATH)
    insert_checkin(conn, ch_id, user_id, shift(today, -3), 3, "根", 22.0)
    insert_checkin(conn, ch_id, user_id, shift(today, -2), 11, "根", 23.0)
    insert_checkin(conn, ch_id, user_id, shift(today, -1), 4, "根", 24.0)
    conn.commit()
    conn.close()

    print("== 3. today 返回 journey 全要素 ==")
    status, body = call("GET", f"/challenges/{ch_id}/today", token=token)
    t = body.get("data", body) if isinstance(body, dict) else {}
    j = t.get("journey") or {}
    check("journey 存在", bool(j), str(t)[:120])
    check("mode=reduction", j.get("mode") == "reduction", str(j.get("mode")))
    check("baseline=25", j.get("baseline") == 25.0, str(j.get("baseline")))
    check("历史少抽=38", j.get("cigarettes_avoided") == 22 + 14 + 21, str(j.get("cigarettes_avoided")))
    check("money_saved≈34", j.get("money_saved") == round((22 + 14 + 21) * 0.9), str(j.get("money_saved")))
    check("money_note 有口径", "18/包" in str(j.get("money_note")), str(j.get("money_note")))
    check("阶梯档位=19/25", j.get("ladder_stage") == 19 and j.get("ladder_total_stages") == 25, f"{j.get('ladder_stage')}/{j.get('ladder_total_stages')}")
    check("goal_date=今天+6", j.get("goal_date") == shift(today, 6), str(j.get("goal_date")))
    check("健康线锚定终点", (j.get("health") or {}).get("anchor_date") == shift(today, 6), str((j.get('health') or {}).get('anchor_date')))
    check("健康线未解锁", all(not m["reached"] for m in (j.get("health") or {}).get("milestones", [])), "")
    check("健康线 6 节点", len((j.get("health") or {}).get("milestones", [])) == 6, "")
    check("里程碑 50 已达(57>=50)", "avoided_50" in [m["key"] for m in j.get("milestones", []) if m["reached"]], str(j.get("milestones")))

    print("== 4. 记一根 → journey 实时更新 ==")
    status, body = call("POST", f"/challenges/{ch_id}/checkin", {"value": 1, "mood": "", "context_tag": "drink"}, token)
    check("记一根 200", status == 200, f"{status} {body}")
    status, body = call("GET", f"/challenges/{ch_id}/today", token=token)
    t = body.get("data", body) if isinstance(body, dict) else {}
    j = t.get("journey") or {}
    check("少抽 +1", j.get("cigarettes_avoided") == 22 + 14 + 21 + 24, str(j.get("cigarettes_avoided")))
    check("today_total=1", t.get("today_total") == 1, str(t.get("today_total")))

    print("== 5. 诱因情境 tag 接受（drink） ==")
    status, body = call("GET", f"/challenges/{ch_id}/today", token=token)
    checkins = t.get("today_checkins") or []
    check("记录带 drink 情境", bool(checkins) and checkins[0].get("context_tag") == "drink", str(checkins[:1]))

    print("== 6. 报告 overview 带旅程 ==")
    status, body = call("GET", f"/challenges/{ch_id}/report/overview", token=token)
    ov = body.get("data", body) if isinstance(body, dict) else {}
    check("overview journey", (ov.get("journey") or {}).get("mode") == "reduction", str(ov.get("journey"))[:80])

    print("== 7. binary 戒断挑战 → quit 模式 + 健康线已解锁 ==")
    status, body = call("POST", "/challenges/confirm", {
        "title": "e2e戒糖", "description": " binary quit", "category": "quit",
        "duration_days": 30, "start_date": shift(today, -20), "source": "manual",
        "task_type": "binary", "scene_template": "quit", "target_value": 1, "unit": "次",
        "direction": "decrease", "goal_type": "soft", "plan": [],
    }, token)
    ch_b = (body.get("data", body) or {}).get("id")
    check("创建戒断挑战", status == 200, f"{status}")
    status, body = call("GET", f"/challenges/{ch_b}/today", token=token)
    t = body.get("data", body) if isinstance(body, dict) else {}
    j = t.get("journey") or {}
    check("mode=quit", j.get("mode") == "quit", str(j.get("mode")))
    check("quit_days=20", j.get("quit_days") == 20, str(j.get("quit_days")))
    health = j.get("health") or {}
    check("健康线锚定开始日", health.get("anchor_date") == shift(today, -20), str(health.get("anchor_date")))
    reached = [m["key"] for m in health.get("milestones", []) if m["reached"]]
    check("20 分钟/12 小时/2 周已达", set(reached) == {"hr_20min", "co_12h", "circ_2w"}, str(reached))

    print("== 8. increase 挑战无 journey ==")
    status, body = call("POST", "/challenges/confirm", {
        "title": "e2e喝水", "description": "increase", "category": "build",
        "duration_days": 7, "start_date": today, "source": "manual",
        "task_type": "counter", "scene_template": "water", "target_value": 8, "unit": "杯",
        "direction": "increase", "goal_type": "hard", "plan": [],
    }, token)
    ch_c = (body.get("data", body) or {}).get("id")
    status, body = call("GET", f"/challenges/{ch_c}/today", token=token)
    t = body.get("data", body) if isinstance(body, dict) else {}
    check("increase journey=None", t.get("journey") is None, str(t.get("journey"))[:60])

    print("== 9. 排行下架探针 ==")
    status, _ = call("GET", "/leaderboard/weekly", token=token)
    check("leaderboard 404/405", status in (404, 405), str(status))
    status, html = call("GET", "/static/js/views/rank.js".replace("/api/v1", ""), token=token)
    check("rank.js 静态 404", status == 404, str(status))
    req = urllib.request.Request("http://127.0.0.1:8610/")
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode()
    check("导航无排行 tab", "switchView('rank')" not in html, "")
    check("无 rank.js 引用", "views/rank.js" not in html, "")

    print("== 10. 清理 ==")
    conn = sqlite3.connect(DB_PATH)
    for cid in (ch_id, ch_b, ch_c):
        conn.execute("DELETE FROM checkins WHERE challenge_id=?", (cid,))
        conn.execute("DELETE FROM challenges WHERE id=?", (cid,))
    if user_id:
        conn.execute("DELETE FROM points_ledger WHERE user_id=?", (str(user_id),))
    conn.commit()
    conn.close()
    check("清理完成", True)

    print(f"\n== 结果: {PASS} passed / {FAIL} failed ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
