from __future__ import annotations

import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8610/api/v1")
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "challenge.db"
TOKEN = os.environ.get("CP_TOKEN", "")

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
    from datetime import datetime, timedelta
    d = datetime.strptime(day, "%Y-%m-%d") + timedelta(days=n)
    return d.strftime("%Y-%m-%d")


def register() -> str:
    name = f"r14rescue{int(__import__('time').time())%1000000}"
    status, body = call("POST", "/auth/register", {"username": name, "password": "R14Rescue#2026", "nickname": name})
    if status != 200:
        status, body = call("POST", "/auth/login", {"username": name, "password": "R14Rescue#2026"})
    data = body.get("data", body) if isinstance(body, dict) else {}
    token = data.get("access_token") or data.get("token") or ""
    assert token, f"register/login failed: {status} {body}"
    return token


def main() -> int:
    global FAIL
    today = __import__("app.services.streak_service", fromlist=["today_str"]).today_str()

    print("== 1. 注册与建挑战 ==")
    token = register()
    status, body = call("POST", "/challenges/confirm", {
        "title": "救援验证英语挑战", "description": "e2e", "category": "learn",
        "duration_days": 66, "start_date": shift(today, -8), "source": "manual",
        "task_type": "word", "scene_template": "english", "target_value": 20, "unit": "词",
        "direction": "increase", "goal_type": "hard", "plan": [],
    }, token)
    check("创建挑战", status == 200, f"{status} {body}")
    data = body.get("data", body) if isinstance(body, dict) else {}
    ch_id = data.get("id")

    print("== 2. 直插历史打卡制造断档（-6 天打卡，-5..-1 断 5 天） ==")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (ch_id, data.get("user_id"), shift(today, -6) + " 10:00:00", 1, shift(today, -6), "completed", "", "", "", "", 100.0, 20, "词"),
    )
    conn.commit()
    conn.close()

    status, body = call("GET", "/challenges", token=token)
    items = body if isinstance(body, list) else body.get("data", [])
    mine = next((x for x in items if x.get("id") == ch_id), {})
    rescue = mine.get("rescue") or {}
    check("列表返回 rescue 信号", rescue.get("missed_days") == 5, str(rescue))
    check("级别 deep（>3 天）", rescue.get("rescue_level") == "deep", str(rescue))
    check("不可一键修复（>1 天）", rescue.get("can_repair") is False, str(rescue))

    print("== 3. 挑战B：断 1 天 → slip + repair 一键补回 ==")
    status, body = call("POST", "/challenges/confirm", {
        "title": "救援验证跑步挑战", "description": "e2e", "category": "fitness",
        "duration_days": 21, "start_date": shift(today, -5), "source": "manual",
        "task_type": "counter", "scene_template": "running", "target_value": 3, "unit": "公里",
        "direction": "increase", "goal_type": "hard", "plan": [],
    }, token)
    check("创建挑战B", status == 200, f"{status}")
    data_b = body.get("data", body) if isinstance(body, dict) else {}
    ch_b = data_b.get("id")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (ch_b, data.get("user_id"), shift(today, -2) + " 10:00:00", 2, shift(today, -2), "completed", "", "", "", "", 100.0, 3, "公里"))
    conn.commit()
    conn.close()
    status, body = call("GET", "/challenges", token=token)
    items = body if isinstance(body, list) else body.get("data", [])
    mine = next((x for x in items if x.get("id") == ch_b), {})
    rescue = mine.get("rescue") or {}
    check("断 1 天 slip", rescue.get("rescue_level") == "slip" and rescue.get("can_repair") is True, str(rescue))
    check("mend_date 指向昨天", rescue.get("mend_date") == shift(today, -1), str(rescue))
    status, body = call("POST", f"/challenges/{ch_b}/repair", None, token)
    ok = (body.get("data", body) or {}).get("ok", False)
    check("repair 成功", status == 200 and ok is True, f"{status} {body}")
    status, body = call("GET", "/challenges", token=token)
    items = body if isinstance(body, list) else body.get("data", [])
    mine = next((x for x in items if x.get("id") == ch_b), {})
    check("repair 后 rescue 清空", not (mine.get("rescue") or {}).get("missed_days"), str(mine.get("rescue")))

    print("== 4. 挑战C：mend 补昨天恢复连续 ==")
    status, body = call("POST", "/challenges/confirm", {
        "title": "救援验证阅读挑战", "description": "e2e", "category": "learn",
        "duration_days": 21, "start_date": shift(today, -5), "source": "manual",
        "task_type": "counter", "scene_template": "reading", "target_value": 30, "unit": "页",
        "direction": "increase", "goal_type": "hard", "plan": [],
    }, token)
    check("创建挑战C", status == 200, f"{status}")
    data_c = body.get("data", body) if isinstance(body, dict) else {}
    ch_c = data_c.get("id")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO checkins (challenge_id, user_id, timestamp, day_number, date, status, mood, reflection, ai_feedback, context_tag, completion_pct, value, unit) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (ch_c, data.get("user_id"), shift(today, -3) + " 10:00:00", 1, shift(today, -3), "completed", "", "", "", "", 100.0, 30, "页"))
    conn.commit()
    conn.close()
    status, body = call("GET", "/challenges", token=token)
    items = body if isinstance(body, list) else body.get("data", [])
    mine = next((x for x in items if x.get("id") == ch_c), {})
    rescue = mine.get("rescue") or {}
    check("挑战C 断 2 天 rescue", rescue.get("missed_days") == 2 and rescue.get("mend_date") == shift(today, -1), str(rescue))
    status, body = call("POST", f"/challenges/{ch_c}/mend", {"date": rescue.get("mend_date")}, token)
    check("mend 补昨天", status == 200, f"{status} {body}")
    status, body = call("GET", "/challenges", token=token)
    items = body if isinstance(body, list) else body.get("data", [])
    mine = next((x for x in items if x.get("id") == ch_c), {})
    check("mend 后连续性恢复 rescue 清空", not (mine.get("rescue") or {}).get("missed_days"), str(mine.get("rescue")))

    print("== 6. 提醒偏好 ==")
    status, body = call("GET", "/challenges/reminder/prefs", token=token)
    check("默认偏好 20 点开启", status == 200 and (body.get("data", body) or {}).get("remind_hour") == 20, f"{status} {body}")
    status, body = call("PUT", "/challenges/reminder/prefs", {"remind_hour": 9, "enabled": True}, token)
    got = body.get("data", body) or {}
    check("更新偏好 9 点", status == 200 and got.get("remind_hour") == 9, f"{status} {body}")
    status, body = call("GET", "/challenges/reminder/prefs", token=token)
    got = body.get("data", body) or {}
    check("回读 9 点", got.get("remind_hour") == 9, str(got))
    status, body = call("PUT", "/challenges/reminder/prefs", {"remind_hour": 5, "enabled": True}, token)
    check("越界小时 422/400", status in (400, 422), f"{status}")

    print("== 7. 下架探针 ==")
    for method, path in [
        ("GET", "/squads/my"),
        ("GET", "/squads"),
        ("POST", "/challenges/datacenter/sync"),
        ("GET", "/portal/today"),
    ]:
        status, _ = call(method, path, {} if method == "POST" else None, token)
        check(f"下架 {method} {path}", status in (401, 404, 405, 422), str(status))

    print("== 8. mood 空值不覆盖 ==")
    status, body = call("POST", f"/challenges/{ch_id}/checkin", {"value": 20, "mood": "bad"}, token)
    check("打卡带 mood bad", status == 200, f"{status}")
    status, body = call("PATCH", f"/challenges/{ch_id}/checkin/today", {"mood": "", "reflection": "今天不错"}, token)
    check("心得空 mood 保存", status == 200, f"{status} {body}")
    status, body = call("GET", f"/challenges/{ch_id}/today", token=token)
    got = body.get("data", body) or {}
    cd = got.get("checkin_data") or {}
    check("mood 保持 bad 不被空值覆盖", cd.get("mood") == "bad", str(cd))
    check("reflection 已写入", cd.get("reflection") == "今天不错", str(cd))

    print(f"\n== 结果: {PASS} passed, {FAIL} failed ==")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
