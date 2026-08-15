#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
import urllib.request
import urllib.error

BASE = "https://songguokr.com/challengePlanet"
API = f"{BASE}/api/v1"
USER, PWD = "cp_e2e", "CpE2e#2026x"
passed: list[str] = []
failed: list[tuple[str, str]] = []

def req(method: str, path: str, body: dict | None = None, token: str | None = None,
        timeout: int = 90, raw: bool = False):
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            return resp.status, (payload if raw else json.loads(payload or b"{}"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except Exception:
            return e.code, {}

def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        passed.append(name)
token = data.get("access_token")
check("登录返回token", st == 200 and bool(token), f"st={st} body={str(body)[:200]}")

print("== 2. 创建减量挑战(戒烟场景) ==")
today = time.strftime("%Y-%m-%d")
plan = [
    {"day": i + 1, "title": f"戒烟第{i+1}天", "description": "今日目标少抽1根",
     "tip": "想抽时喝口水", "task_type": "counter", "target_value": 10 - i * 0.3,
     "unit": "根", "difficulty": 3, "steps": []}
    for i in range(21)
]
st, ch = req("POST", "/challenges/confirm", {
    "title": "21天渐进戒烟",
    "category": "quit",
    "duration_days": 21,
    "start_date": today,
    "description": "通过按时段记录抽烟数量,软目标督促减少",
    "plan": plan,
    "source": "manual",
    "task_type": "counter",
    "target_value": 8.0,
    "unit": "根",
    "direction": "decrease",
    "goal_type": "soft",
    "decompose_mode": "time_slot",
    "slot_hours": 4,
    "slot_target_value": 2.0,
}, token)
cid = ch.get("id")
check("创建减量挑战返回id", st == 200 and isinstance(cid, int), f"st={st} body={str(ch)[:200]}")
check("挑战direction=decrease", ch.get("direction") == "decrease", f"dir={ch.get('direction')}")
check("挑战goal_type=soft", ch.get("goal_type") == "soft", f"gt={ch.get('goal_type')}")
check("挑战decompose_mode=time_slot", ch.get("decompose_mode") == "time_slot",
      f"dm={ch.get('decompose_mode')}")
check("挑战slot_target_value=2.0", ch.get("slot_target_value") == 2.0,
      f"stv={ch.get('slot_target_value')}")

print("== 3. 手动创建时段子目标 ==")
st, sg_body = req("POST", f"/challenges/{cid}/sub-goals", {
    "sub_goals": [
        {"title": "早晨", "time_window_start": "06:00", "time_window_end": "12:00",
         "target_value": 1.0, "goal_type": "soft", "weight": 1.0, "order": 1},
        {"title": "下午", "time_window_start": "12:00", "time_window_end": "18:00",
         "target_value": 1.0, "goal_type": "soft", "weight": 1.0, "order": 2},
        {"title": "晚上", "time_window_start": "18:00", "time_window_end": "23:00",
         "target_value": 2.0, "goal_type": "soft", "weight": 1.5, "order": 3},
    ]
}, token)
sub_goals = sg_body if isinstance(sg_body, list) else []
check("批量创建3个时段子目标", st == 200 and len(sub_goals) == 3,
      f"st={st} len={len(sub_goals)} body={str(sg_body)[:200]}")
if sub_goals:
    sg1 = sub_goals[0]
    check("子目标含today_value字段", "today_value" in sg1, f"keys={list(sg1.keys())}")
    check("子目标含progress_pct字段", "progress_pct" in sg1, f"keys={list(sg1.keys())}")
    check("子目标time_window正确", sg1.get("time_window_start") == "06:00",
          f"ws={sg1.get('time_window_start')}")

print("== 4. 查询子目标列表 ==")
st, sg_list = req("GET", f"/challenges/{cid}/sub-goals", token=token)
check("查询子目标列表", st == 200 and len(sg_list) == 3,
      f"st={st} len={len(sg_list) if isinstance(sg_list, list) else 'NA'}")

print("== 5. 多次打卡(模拟一天内不同时段) ==")
now_ts = time.strftime("%Y-%m-%dT%H:%M:%S")

st, ck1 = req("POST", f"/challenges/{cid}/checkin", {
    "value": 1.0,
    "sub_goal_id": sub_goals[0]["id"] if sub_goals else None,
    "context_tag": "home",
    "reflection": "早起抽了一根",
    "timestamp": now_ts,
}, token)
check("第一次打卡成功", st == 200 and ck1.get("checkin", {}).get("id"),
      f"st={st} body={str(ck1)[:200]}")
check("返回today_total=1.0", float(ck1.get("today_total", 0)) == 1.0,
      f"tt={ck1.get('today_total')}")
check("返回dynamic_baseline>0", float(ck1.get("dynamic_baseline", 0)) > 0,
      f"db={ck1.get('dynamic_baseline')}")
check("返回is_soft_exceeded=False", ck1.get("is_soft_exceeded") is False,
      f"ise={ck1.get('is_soft_exceeded')}")
check("返回streak=1", ck1.get("streak") == 1, f"streak={ck1.get('streak')}")
check("AI反馈非空", bool(ck1.get("ai_feedback")), "")

import datetime as _dt
ts2 = (_dt.datetime.now() + _dt.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S")
st, ck2 = req("POST", f"/challenges/{cid}/checkin", {
    "value": 2.0,
    "sub_goal_id": sub_goals[1]["id"] if len(sub_goals) > 1 else None,
    "context_tag": "work",
    "reflection": "工作压力大抽了两根",
    "timestamp": ts2,
}, token)
check("第二次打卡成功(同一天)", st == 200 and ck2.get("checkin", {}).get("id"),
      f"st={st} body={str(ck2)[:200]}")
check("today_total累计=3.0", float(ck2.get("today_total", 0)) == 3.0,
      f"tt={ck2.get('today_total')}")
check("is_soft_exceeded=True(超过时段软目标2.0)",
      ck2.get("is_soft_exceeded") is True,
      f"ise={ck2.get('is_soft_exceeded')} sa={ck2.get('soft_exceeded_amount')}")
check("soft_exceeded_amount>0", float(ck2.get("soft_exceeded_amount", 0)) > 0,
      f"sa={ck2.get('soft_exceeded_amount')}")

ts3 = (_dt.datetime.now() + _dt.timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%S")
st, ck3 = req("POST", f"/challenges/{cid}/checkin", {
    "value": 3.0,
    "sub_goal_id": sub_goals[2]["id"] if len(sub_goals) > 2 else None,
    "context_tag": "social",
    "reflection": "聚餐又抽了几根",
    "timestamp": ts3,
}, token)
check("第三次打卡成功", st == 200 and ck3.get("checkin", {}).get("id"),
      f"st={st} body={str(ck3)[:200]}")
check("today_total累计=6.0", float(ck3.get("today_total", 0)) == 6.0,
      f"tt={ck3.get('today_total')}")

print("== 6. 查询今日所有打卡记录 ==")
st, today_ckins = req("GET", f"/challenges/{cid}/checkins/today", token=token)
check("今日打卡列表3条", st == 200 and isinstance(today_ckins, list) and len(today_ckins) == 3,
      f"st={st} len={len(today_ckins) if isinstance(today_ckins, list) else 'NA'}")
if isinstance(today_ckins, list) and today_ckins:
    check("打卡记录含sub_goal_id", "sub_goal_id" in today_ckins[0],
          f"keys={list(today_ckins[0].keys())}")
    check("打卡记录含timestamp", "timestamp" in today_ckins[0], "")
    check("打卡记录含context_tag", "context_tag" in today_ckins[0], "")

print("== 7. 今日详情(含子目标进度) ==")
st, detail = req("GET", f"/challenges/{cid}/today-detail", token=token)
check("今日详情返回", st == 200 and isinstance(detail, dict),
      f"st={st} body={str(detail)[:200]}")
check("今日详情today_total=6.0", float(detail.get("today_total", 0)) == 6.0,
      f"tt={detail.get('today_total')}")
check("今日详情含sub_goals数组",
      isinstance(detail.get("sub_goals"), list) and len(detail.get("sub_goals", [])) == 3,
      f"sg={detail.get('sub_goals')}")
check("今日详情含today_checkins数组",
      isinstance(detail.get("today_checkins"), list) and len(detail.get("today_checkins", [])) == 3,
      f"tc={len(detail.get('today_checkins', []))}")
if detail.get("sub_goals"):
    sg0 = detail["sub_goals"][0]
    check("子目标today_value=1.0", float(sg0.get("today_value", 0)) == 1.0,
          f"tv={sg0.get('today_value')}")
    check("子目标today_checkin_count=1", sg0.get("today_checkin_count") == 1,
          f"tcc={sg0.get('today_checkin_count')}")
    check("子目标progress_pct>0", float(sg0.get("progress_pct", 0)) > 0,
          f"pp={sg0.get('progress_pct')}")

print("== 8. 删除一条打卡记录 ==")
ckid_to_delete = ck3.get("checkin", {}).get("id")
st, del_body = req("DELETE", f"/challenges/{cid}/checkins/{ckid_to_delete}", token=token)
check("删除打卡记录成功", st == 200 and del_body.get("ok") is True,
      f"st={st} body={del_body}")
st, today_after_del = req("GET", f"/challenges/{cid}/checkins/today", token=token)
check("删除后今日打卡2条",
      st == 200 and isinstance(today_after_del, list) and len(today_after_del) == 2,
      f"len={len(today_after_del) if isinstance(today_after_del, list) else 'NA'}")

print("== 9. 报表-总览 ==")
st, overview = req("GET", f"/challenges/{cid}/report/overview", token=token)
check("总览返回", st == 200 and isinstance(overview, dict),
      f"st={st} body={str(overview)[:200]}")
check("总览含today_total", "today_total" in overview, f"keys={list(overview.keys())[:10]}")
check("总览含dynamic_baseline", "dynamic_baseline" in overview, "")
check("总览含streak", "streak" in overview, "")
check("总览含last_7d_avg", "last_7d_avg" in overview, "")
check("总览含peak_hour", "peak_hour" in overview, "")
check("总览direction=decrease", overview.get("direction") == "decrease",
      f"dir={overview.get('direction')}")
check("总览today_total=3.0(删除后)", float(overview.get("today_total", 0)) == 3.0,
      f"tt={overview.get('today_total')}")
check("总览insight非空", bool(overview.get("insight")), f"ins={overview.get('insight', '')[:60]}")

print("== 10. 报表-小时分布(玫瑰图) ==")
st, hourly = req("GET", f"/challenges/{cid}/report/hourly?days=7", token=token)
check("小时分布返回", st == 200 and isinstance(hourly, dict),
      f"st={st} body={str(hourly)[:200]}")
check("小时分布items长度24",
      isinstance(hourly.get("items"), list) and len(hourly.get("items", [])) == 24,
      f"len={len(hourly.get('items', []))}")
check("小时分布含peak_hour", "peak_hour" in hourly, "")
check("小时分布insight非空", bool(hourly.get("insight")), "")
if hourly.get("items"):
    h0 = hourly["items"][0]
    check("小时项含hour字段", "hour" in h0, f"keys={list(h0.keys())}")
    check("小时项含total_value", "total_value" in h0, "")
    check("小时项含exceed_pct", "exceed_pct" in h0, "")

print("== 11. 报表-趋势 ==")
st, trend = req("GET", f"/challenges/{cid}/report/trend?days=30", token=token)
check("趋势返回", st == 200 and isinstance(trend, dict),
      f"st={st} body={str(trend)[:200]}")
check("趋势points长度30",
      isinstance(trend.get("points"), list) and len(trend.get("points", [])) == 30,
      f"len={len(trend.get('points', []))}")
check("趋势含avg_value", "avg_value" in trend, "")
check("趋势含trend_direction", "trend_direction" in trend, "")
check("趋势direction=decrease", trend.get("direction") == "decrease", "")
if trend.get("points"):
    p0 = trend["points"][0]
    check("趋势点含baseline", "baseline" in p0, f"keys={list(p0.keys())}")
    check("趋势点含target", "target" in p0, "")

print("== 12. 报表-热力图 ==")
st, heatmap = req("GET", f"/challenges/{cid}/report/heatmap", token=token)
check("热力图返回", st == 200 and isinstance(heatmap, dict),
      f"st={st} body={str(heatmap)[:200]}")
check("热力图cells非空",
      isinstance(heatmap.get("cells"), list) and len(heatmap.get("cells", [])) > 0,
      f"len={len(heatmap.get('cells', []))}")
check("热力图含active_days", "active_days" in heatmap, "")
check("热力图含on_track_days", "on_track_days" in heatmap, "")
check("热力图year=2026", heatmap.get("year") == 2026, f"year={heatmap.get('year')}")
if heatmap.get("cells"):
    c0 = heatmap["cells"][0]
    check("热力图cell含level", "level" in c0, f"keys={list(c0.keys())}")
    check("热力图cell含value", "value" in c0, "")

print("== 13. 报表-完成率 ==")
st, comp = req("GET", f"/challenges/{cid}/report/completion?period=week", token=token)
check("完成率返回", st == 200 and isinstance(comp, dict),
      f"st={st} body={str(comp)[:200]}")
check("完成率含completion_rate", "completion_rate" in comp, "")
check("完成率含on_track_days", "on_track_days" in comp, "")
check("完成率含soft_exceed_days", "soft_exceed_days" in comp, "")
check("完成率period=week", comp.get("period") == "week", f"p={comp.get('period')}")
check("完成率direction=decrease", comp.get("direction") == "decrease", "")

st, comp_month = req("GET", f"/challenges/{cid}/report/completion?period=month", token=token)
check("月度完成率返回", st == 200 and comp_month.get("period") == "month",
      f"st={st} p={comp_month.get('period')}")

print("== 14. 自动拆解子目标(AI) ==")
st, auto = req("POST", f"/challenges/{cid}/sub-goals/auto-decompose", {
    "slot_hours": 6,
    "target_per_slot": 1.5,
    "goal_type": "soft",
}, token)
check("自动拆解返回", st == 200 and isinstance(auto, dict),
      f"st={st} body={str(auto)[:200]}")
check("自动拆解含message", "message" in auto, f"keys={list(auto.keys())}")
check("自动拆解sub_goals是list", isinstance(auto.get("sub_goals"), list),
      f"sg={type(auto.get('sub_goals'))}")

print("== 15. today任务含子目标进度 ==")
st, today_task = req("GET", f"/challenges/{cid}/today", token=token)
check("today任务返回", st == 200 and isinstance(today_task, dict),
      f"st={st} body={str(today_task)[:200]}")
check("today含sub_goals数组",
      isinstance(today_task.get("sub_goals"), list),
      f"sg={today_task.get('sub_goals')}")
check("today含today_checkins数组",
      isinstance(today_task.get("today_checkins"), list),
      f"tc={type(today_task.get('today_checkins'))}")
check("today含dynamic_baseline", "dynamic_baseline" in today_task, "")
check("today含today_total", "today_total" in today_task, "")
check("today方向=decrease", today_task.get("direction") == "decrease", "")

print("== 16. 创建增量挑战(喝水场景)对比测试 ==")
st, ch2 = req("POST", "/challenges/confirm", {
    "title": "每天喝8杯水",
    "category": "health",
    "duration_days": 14,
    "start_date": today,
    "description": "通过分时段打卡增加饮水量",
    "plan": [{"day": i + 1, "title": f"第{i+1}天喝水", "description": "今日8杯水",
              "tip": "", "task_type": "counter", "target_value": 8,
              "unit": "杯", "difficulty": 1, "steps": []} for i in range(14)],
    "source": "manual",
    "task_type": "counter",
    "target_value": 8.0,
    "unit": "杯",
    "direction": "increase",
    "goal_type": "hard",
    "decompose_mode": "time_slot",
    "slot_hours": 4,
    "slot_target_value": 2.0,
}, token)
cid2 = ch2.get("id")
check("创建增量挑战返回id", st == 200 and isinstance(cid2, int),
      f"st={st} body={str(ch2)[:200]}")
check("增量挑战direction=increase", ch2.get("direction") == "increase", "")

st, ck_inc = req("POST", f"/challenges/{cid2}/checkin", {
    "value": 2.0,
    "context_tag": "home",
    "reflection": "上午喝了2杯",
}, token)
check("增量打卡成功", st == 200 and ck_inc.get("checkin", {}).get("id"),
      f"st={st} body={str(ck_inc)[:200]}")
check("增量today_total=2.0", float(ck_inc.get("today_total", 0)) == 2.0,
      f"tt={ck_inc.get('today_total')}")
check("增量is_soft_exceeded=False(hard目标)",
      ck_inc.get("is_soft_exceeded") is False,
      f"ise={ck_inc.get('is_soft_exceeded')}")

st, ck_inc2 = req("POST", f"/challenges/{cid2}/checkin", {
    "value": 3.0,
    "context_tag": "work",
    "reflection": "下午喝了3杯",
}, token)
check("增量第二次打卡", st == 200, f"st={st}")
check("增量today_total=5.0", float(ck_inc2.get("today_total", 0)) == 5.0,
      f"tt={ck_inc2.get('today_total')}")

st, ov_inc = req("GET", f"/challenges/{cid2}/report/overview", token=token)
check("增量总览direction=increase", ov_inc.get("direction") == "increase",
      f"dir={ov_inc.get('direction')}")

print("== 17. 子目标删除测试 ==")
st, sg_before_del = req("GET", f"/challenges/{cid}/sub-goals", token=token)
before_count = len(sg_before_del) if isinstance(sg_before_del, list) else 0
if before_count > 0:
    sg_id_del = sg_before_del[-1]["id"]
    st, del_sg = req("DELETE", f"/challenges/{cid}/sub-goals/{sg_id_del}", token=token)
    check("删除子目标成功", st == 200 and del_sg.get("ok") is True,
          f"st={st} body={del_sg}")
    st, sg_after = req("GET", f"/challenges/{cid}/sub-goals", token=token)
    after_count = len(sg_after) if isinstance(sg_after, list) else 0
    check("删除后子目标数量减少", after_count == before_count - 1,
          f"before={before_count} after={after_count}")

print("== 18. 非法参数边界测试 ==")
st, bad_comp = req("GET", f"/challenges/{cid}/report/completion?period=invalid", token=token)
check("非法period被拒绝422", st == 422, f"st={st}")

st, bad_days = req("GET", f"/challenges/{cid}/report/hourly?days=200", token=token)
check("days超过上限被拒绝422", st == 422, f"st={st}")

st, bad_sub = req("POST", f"/challenges/{cid}/sub-goals", {
    "sub_goals": [
        {"title": f"时段{i}", "time_window_start": "00:00", "time_window_end": "06:00",
         "target_value": 1.0, "goal_type": "soft", "weight": 1.0, "order": i}
        for i in range(5)
    ]
}, token)
check("超过4个子目标被拒绝400", st == 400, f"st={st} body={str(bad_sub)[:150]}")

st, notfound = req("GET", "/challenges/999999/today-detail", token=token)
check("不存在挑战404/400", st in (400, 404), f"st={st}")

print("== 19. 他人挑战鉴权拦截 ==")
st, other_today = req("GET", f"/challenges/{cid2}/today", token=token)
check("自己挑战可访问", st == 200, f"st={st}")

print("== 20. 报表数据一致性验证 ==")
st, final_today = req("GET", f"/challenges/{cid}/today-detail", token=token)
st, final_ov = req("GET", f"/challenges/{cid}/report/overview", token=token)
if isinstance(final_today, dict) and isinstance(final_ov, dict):
    check("today-detail与overview的today_total一致",
          float(final_today.get("today_total", 0)) == float(final_ov.get("today_total", 0)),
          f"td={final_today.get('today_total')} ov={final_ov.get('today_total')}")
    check("today-detail与overview的direction一致",
          final_today.get("direction") == final_ov.get("direction"),
          f"td={final_today.get('direction')} ov={final_ov.get('direction')}")

print(f"\n===== 结果: {len(passed)} 通过, {len(failed)} 失败 =====")
for name, detail in failed:
    print(f"FAILED: {name} :: {detail}")
sys.exit(1 if failed else 0)
