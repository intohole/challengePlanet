import json
import os
import sqlite3
import sys
import time
import urllib.request

BASE = os.environ.get("CP_BASE", "http://127.0.0.1:8600/api/v1")
DB = os.environ.get(
    "CP_DB", "/home/cool/workspace/miniDeploy/apps/challengePlanet/extracted/data/challenge.db"
)
TOKEN = open(os.environ.get("CP_TOKEN_FILE", "/tmp/cp_token.txt")).read().strip()
try:
    UID = open(os.environ.get("CP_UID_FILE", "/tmp/cp_uid.txt")).read().strip()
except OSError:
    UID = "156"
H = {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"}

passed = []
failed = []


def check(name, cond, extra=""):
    if cond:
        passed.append(name)
        print("PASS", name, extra)
    else:
        failed.append(name)
        print("FAIL", name, extra)


def req(method, path, body=None, timeout=90):
    r = urllib.request.Request(BASE + path, method=method, headers=H)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, data=data, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, {"raw": raw}


def sse_create(raw_input):
    r = urllib.request.Request(BASE + "/challenges/nl-create", method="POST", headers=H,
                               data=json.dumps({"raw_input": raw_input}).encode())
    plan, parsed = [], {}
    with urllib.request.urlopen(r, timeout=120) as resp:
        for line in resp:
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except ValueError:
                continue
            if evt.get("step") == "preview":
                plan = evt.get("plan", [])
                parsed = evt.get("parsed", {})
    return parsed, plan


today = time.strftime("%Y-%m-%d")

print("== 1. 创建挑战(SSE流式) ==")
parsed, plan = sse_create("21天每天背20个英语单词")
check("SSE解析标题", bool(parsed.get("title")), str(parsed.get("title")))
check("SSE生成计划天数", len(plan) >= 7, "days=%d" % len(plan))

st, ch = req("POST", "/challenges/confirm", {
    "title": parsed.get("title") or "背单词挑战",
    "category": parsed.get("category") or "learn",
    "duration_days": len(plan) or 7,
    "description": parsed.get("description") or "每天背20个英语单词",
    "plan": plan,
    "start_date": today,
})
check("确认创建挑战", st == 200 and ch.get("id"), "id=%s" % ch.get("id"))
cid = ch["id"]

print("== 2. 今日任务 ==")
st, t = req("GET", "/challenges/%d/today" % cid)
check("今日任务返回", st == 200 and t.get("task_title"), str(t.get("task_title"))[:30])
check("今日未打卡", t.get("checked_in") is False)

print("== 3. 点火打卡(full) ==")
st, r = req("POST", "/challenges/%d/checkin" % cid, {"checkin_type": "full", "mood": "good", "reflection": "第一天感觉不错"})
check("打卡成功", st == 200 and r.get("checkin", {}).get("id"), "streak=%s" % r.get("streak"))
check("打卡类型=full", r.get("checkin", {}).get("checkin_type") == "full")
check("返回宣言字段", "declaration" in r, repr(r.get("declaration"))[:40])
check("返回护盾字段", "shields" in r, "shields=%s" % r.get("shields"))
check("积分>0", r.get("points_earned", 0) > 0, "pts=%s" % r.get("points_earned"))
check("AI反馈非空", bool(r.get("ai_feedback")), str(r.get("ai_feedback"))[:30])

st, r2 = req("POST", "/challenges/%d/checkin" % cid, {"checkin_type": "full"})
check("重复打卡拦截", r2.get("already_checked") is True)

print("== 4. 微打卡(mini) ==")
parsed2, plan2 = sse_create("7天每天拉伸5分钟")
dur2 = int(parsed2.get("duration_days") or 7)
if len(plan2) < dur2:
    for d in range(len(plan2) + 1, dur2 + 1):
        plan2.append({"day": d, "title": "拉伸5分钟", "description": "完成5分钟全身拉伸", "tip": ""})
st, ch2 = req("POST", "/challenges/confirm", {
    "title": parsed2.get("title") or "拉伸挑战",
    "category": "fitness",
    "duration_days": dur2,
    "description": "每天拉伸5分钟",
    "plan": plan2,
    "start_date": today,
})
cid2 = ch2["id"]
st, rm = req("POST", "/challenges/%d/checkin" % cid2, {"checkin_type": "mini", "mood": "bad"})
check("微打卡成功", st == 200 and rm.get("checkin", {}).get("checkin_type") == "mini")
check("微打卡默认心得", bool(rm.get("checkin", {}).get("reflection")), rm.get("checkin", {}).get("reflection"))
mini_pts = rm.get("points_earned", 0)
print("   mini积分:", mini_pts)

print("== 5. 自适应建议(bad心情x2触发) ==")
con = sqlite3.connect(DB)
yday = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
con.execute(
    "INSERT INTO checkins (challenge_id, user_id, day_number, date, status, checkin_type, mood, reflection, ai_feedback, created_at) "
    "VALUES (?, ?, 0, ?, 'completed', 'full', 'bad', '太累了不想背', '', datetime('now'))",
    (cid2, UID, yday))
con.commit()
con.close()
st, _ = req("PATCH", "/challenges/%d/checkin/today" % cid2, {"mood": "bad", "reflection": "今天也很吃力"})
check("心情更新为bad", st == 200)
for _ in range(10):
    time.sleep(2)
    st, ap = req("GET", "/challenges/%d/adaptive/pending" % cid2)
    if ap.get("suggestion"):
        break
st, ap = req("GET", "/challenges/%d/adaptive/pending" % cid2)
sug = ap.get("suggestion")
check("生成减负建议", sug is not None, json.dumps(sug, ensure_ascii=False)[:80] if sug else "None")
if sug:
    check("建议含新任务", bool(sug.get("task", {}).get("title")), sug.get("task", {}).get("title"))
    check("建议目标明天", sug.get("target_day", 0) >= 1, "day=%s" % sug.get("target_day"))
    st, rr = req("POST", "/challenges/%d/adaptive/%d/respond" % (cid2, sug["id"]), {"accept": True})
    check("采纳建议", st == 200 and rr.get("applied") is True)
    st, ap2 = req("GET", "/challenges/%d/adaptive/pending" % cid2)
    check("建议已消费", ap2.get("suggestion") is None)

print("== 6. 断签诊断 ==")
con = sqlite3.connect(DB)
start5 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 5 * 86400))
plan21 = json.dumps([{"day": i + 1, "title": "学习第%d天" % (i + 1), "description": "专注学习30分钟", "tip": ""} for i in range(21)], ensure_ascii=False)
cur = con.execute(
    "INSERT INTO challenges (user_id, title, category, duration_days, description, ai_plan, start_date, end_date, status, color, icon, is_shared, share_token, created_at) "
    "VALUES (?, ?, 'learn', 21, '测试断签', ?, ?, ?, 'active', '#6366f1', '🎯', 0, '', datetime('now'))",
    (UID, "断签诊断测试挑战", plan21, start5, time.strftime("%Y-%m-%d", time.localtime(time.time() + 15 * 86400))))
cid3 = cur.lastrowid
for i in (0, 1):
    ds = time.strftime("%Y-%m-%d", time.localtime(time.time() - (5 - i) * 86400))
    con.execute(
        "INSERT INTO checkins (challenge_id, user_id, day_number, date, status, checkin_type, mood, reflection, ai_feedback, created_at) "
        "VALUES (?, ?, ?, ?, 'completed', 'full', 'normal', '加班太多没时间', '', datetime('now'))",
        (cid3, UID, i + 1, ds))
con.commit()
con.close()
st, dg = req("POST", "/challenges/%d/diagnose" % cid3, {})
check("诊断返回原因", st == 200 and bool(dg.get("cause_label")), dg.get("cause_label"))
check("诊断含叙事", bool(dg.get("narrative")), str(dg.get("narrative"))[:40])
check("断签天数>=3", dg.get("missed_count", 0) >= 3, "missed=%s" % dg.get("missed_count"))
check("建议方案合法", dg.get("suggestion_action") in ("lighten3", "micro", "keep"), dg.get("suggestion_action"))
act = dg.get("suggestion_action") or "keep"
st, aply = req("POST", "/challenges/%d/diagnose/apply" % cid3, {"action": act})
check("应用诊断方案", st == 200 and aply.get("ok") is True, aply.get("message"))
st, latest = req("GET", "/challenges/%d/diagnosis" % cid3)
check("查询最新诊断", st == 200 and latest.get("report", {}).get("cause_label") == dg.get("cause_label"))

print("== 7. 护盾里程碑(streak=7) ==")
con = sqlite3.connect(DB)
start6 = time.strftime("%Y-%m-%d", time.localtime(time.time() - 6 * 86400))
cur = con.execute(
    "INSERT INTO challenges (user_id, title, category, duration_days, description, ai_plan, start_date, end_date, status, color, icon, is_shared, share_token, created_at) "
    "VALUES (?, '护盾测试挑战', 'build', 21, '测试护盾', '[]', ?, ?, 'active', '#6366f1', '🎯', 0, '', datetime('now'))",
    (UID, start6, time.strftime("%Y-%m-%d", time.localtime(time.time() + 14 * 86400))))
cid4 = cur.lastrowid
for i in range(6):
    ds = time.strftime("%Y-%m-%d", time.localtime(time.time() - (6 - i) * 86400))
    con.execute(
        "INSERT INTO checkins (challenge_id, user_id, day_number, date, status, checkin_type, mood, reflection, ai_feedback, created_at) "
        "VALUES (?, ?, ?, ?, 'completed', 'full', 'good', '坚持', '', datetime('now'))",
        (cid4, UID, i + 1, ds))
con.commit()
con.close()
st, rs = req("POST", "/challenges/%d/checkin" % cid4, {"checkin_type": "full", "mood": "good"})
check("连续7天打卡", st == 200 and rs.get("streak") == 7, "streak=%s" % rs.get("streak"))
check("获得里程碑护盾", rs.get("shields", 0) >= 1, "shields=%s" % rs.get("shields"))
st, mc = req("GET", "/challenges/%d/mercy" % cid4)
check("mercy返回护盾数", mc.get("shields", 0) >= 1, "shields=%s" % mc.get("shields"))

print()
print("通过 %d / %d" % (len(passed), len(passed) + len(failed)))
if failed:
    print("失败项:", failed)
    sys.exit(1)
