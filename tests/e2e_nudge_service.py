from __future__ import annotations

import sys

sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

from app.services.nudge_service import NudgeService


class FakeCh:
    def __init__(self, direction="decrease", unit="根", goal_rule="ladder",
                 ladder_goal=0.0, ladder_start=0.0, duration_days=30,
                 ladder_interval=3, ladder_step=1.0):
        self.direction = direction
        self.unit = unit
        self.goal_rule = goal_rule
        self.ladder_goal = ladder_goal
        self.ladder_start = ladder_start
        self.duration_days = duration_days
        self.ladder_interval = ladder_interval
        self.ladder_step = ladder_step


svc = NudgeService()
fails = 0


def chk(name, got, want):
    global fails
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "=>", got)
    if not ok:
        fails += 1


r = svc.evaluate(FakeCh(), 4, 5, hour=10, today_count=4)
chk("decrease 10点已4根 enabled", r["enabled"], True)
chk("decrease 10点已4根 projected", r["projected"], 18.0)
chk("decrease 10点已4根 risk=1", r["risk_level"], 1)
chk("decrease 10点已4根 触顶11:00", r["touch_at"], "11:00")
chk("decrease 10点已4根 剩余弹性1h", r["remaining_hours"], 1.0)
chk("decrease 10点已4根 剩余配额1", r["remaining_units"], 1.0)
chk("decrease 10点已4根 nudge_level=1", r["nudge_level"], 1)
chk("decrease 10点已4根 非静默", r["quiet"], False)

r = svc.evaluate(FakeCh(), 4, 5, hour=10, today_count=1)
chk("decrease 样本不足 quiet", r["quiet"], True)
chk("decrease 样本不足 不出预计", r["projected"], 0.0)
chk("decrease 样本不足 不出触顶", r["touch_at"], "")

r = svc.evaluate(FakeCh(), 2, 20, hour=10, today_count=3)
chk("decrease 在计划内 不出触顶", r["touch_at"], "")
chk("decrease 在计划内 risk=0", r["risk_level"], 0)

r = svc.evaluate(FakeCh(), 2, 12, hour=2, today_count=2)
chk("decrease 凌晨静默 quiet", r["quiet"], True)
chk("decrease 凌晨静默 不出预计", r["projected"], 0.0)
chk("decrease 凌晨静默 无话术", r["coach_nudge"], "")
chk("decrease 凌晨静默 仍给还可", r["remaining_units"], 10.0)

r = svc.evaluate(FakeCh(), 6, 5, hour=15, today_count=6)
chk("decrease 已超限 risk=2", r["risk_level"], 2)
chk("decrease 已超限 话术严厉", r["coach_nudge"], "今天已超 1根。停下来，别再继续了")

r = svc.evaluate(FakeCh(), 5, 5, hour=15, today_count=5)
chk("decrease 到顶 risk=2", r["risk_level"], 2)
chk("decrease 到顶 话术严厉", r["coach_nudge"], "今天已到上限 5根，就此打住")

r = svc.evaluate(FakeCh(), 2, 20, hour=14, today_count=2)
chk("decrease 安全 risk=0", r["risk_level"], 0)
chk("decrease 安全 无话术", r["coach_nudge"], "")

r = svc.evaluate(FakeCh(), 0, 8, hour=20, today_count=0)
chk("decrease 无记录 disabled", r["enabled"], False)

rows = [{"hour": h, "total_value": 2.0 if h in (8, 9, 10) else 0.3} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 4, 5, hour=11, hour_dist=rows, today_count=4)
chk("decrease 时段加权 projected>5", r["projected"] > 5.0, True)
chk("decrease 时段加权 risk=1", r["risk_level"], 1)

rows_sparse = [{"hour": 20, "total_value": 60.0, "checkin_count": 10},
               {"hour": 21, "total_value": 40.0, "checkin_count": 6},
               {"hour": 22, "total_value": 30.0, "checkin_count": 5}]
r = svc.evaluate(FakeCh(), 2, 5, hour=10, hour_dist=rows_sparse, today_count=2)
chk("decrease 稀疏分布 不极端放大", r["projected"] <= 20, True)
chk("decrease 稀疏分布 上午10点预计9根", round(r["projected"]), 9)

night_share = {1: 10.0, 2: 10.0, 8: 6.0, 9: 8.0, 10: 13.0, 12: 13.0,
               16: 8.0, 19: 4.0, 20: 16.0, 21: 4.0, 22: 4.0, 23: 4.0}
rows_with_night = [{"hour": h, "total_value": night_share[h]} for h in sorted(night_share)]
rows_no_night = [{"hour": h, "total_value": night_share[h]} for h in sorted(night_share) if h >= 6]
r_night = svc.evaluate(FakeCh(), 4, 20, hour=10, hour_dist=rows_with_night, today_count=4)
r_plain = svc.evaluate(FakeCh(), 4, 20, hour=10, hour_dist=rows_no_night, today_count=4)
chk("凌晨时段纳入画像 预计不再被放大", r_night["projected"] < r_plain["projected"], True)
chk("凌晨时段纳入画像 预计接近日常水平", round(r_night["projected"]), 12)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 2, 5, hour=21, today_count=2)
chk("increase 20点后未达标 level", r["nudge_level"], 1)
chk("increase 20点后话术", r["coach_nudge"], "今天还差3组，现在补上，今晚睡得踏实")

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 1, 5, hour=18, today_count=1)
chk("increase 17点未过半 level", r["nudge_level"], 1)
chk("increase 17点未过半话术", r["coach_nudge"], "今天进度还没过半，还差4组，趁现在抓紧就达标了")

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 5, 5, hour=21, today_count=5)
chk("increase 已达标不提醒", r["nudge_level"], 0)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 7, 5, hour=14, is_soft_exceeded=True, today_count=7)
chk("increase soft超限不提醒", r["nudge_level"], 0)

rows_wd = [{"hour": 14, "total_value": 3.0, "checkin_count": 3},
           {"hour": 15, "total_value": 3.0, "checkin_count": 3},
           {"hour": 16, "total_value": 2.0, "checkin_count": 2},
           {"hour": 9, "total_value": 1.0, "checkin_count": 1}]
r = svc.evaluate(FakeCh(), 4, 5, hour=10, hour_dist=rows, weekday_dist=rows_wd, today_count=4)
chk("decrease 星期加权 basis", r["basis"], "按你最近两周的同时段节奏")
chk("decrease 星期加权 confidence>0", r["confidence"] > 0, True)
chk("decrease 星期加权 有预计值", r["projected"] > 0, True)

r = svc.evaluate(FakeCh(), 4, 5, hour=10, hour_dist=rows, today_count=4)
chk("decrease 全量分布 basis", r["basis"], "按你最近两周的节奏")
chk("decrease 全量分布 高把握", r["confidence_label"], "高")
chk("decrease 全量分布 无区间字段", "projected_low" not in r, True)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 3, 5, hour=12, today_count=3)
chk("increase 12点已3组 达标时刻", r["reach_at"], "16:00")
chk("increase 12点已3组 今日预计", r["projected"], 9.0)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 1, 20, hour=21, today_count=1)
chk("increase 21点进度太慢 无达标时刻", r["reach_at"], "")
chk("increase 21点进度太慢 nudge=1", r["nudge_level"], 1)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 3, 8, hour=2, hour_dist=rows, today_count=3)
chk("increase 凌晨静默 不出达标时刻", r["reach_at"], "")

ch = FakeCh(ladder_start=20.0, ladder_goal=5.0, duration_days=45)
r = svc.evaluate(ch, 4, 18, hour=10, hour_dist=rows, day_number=15, recent_avg=20.0, today_count=4)
lo = r["ladder_outlook"]
chk("ladder 跟上计划 未达标", lo["on_track"], False)
chk("ladder 跟上计划 计划上限约17", round(lo["plan_cap"]), 17)
chk("ladder 跟上计划 剩余天数", lo["remaining_days"], 30)
chk("ladder 跟上计划 话术讲对比", "比阶梯计划高" in lo["message"], True)
chk("ladder 跟上计划 无多余小数", ".0" not in lo["message"], True)

r = svc.evaluate(ch, 4, 18, hour=10, hour_dist=rows, day_number=15, recent_avg=6.0, today_count=4)
lo = r["ladder_outlook"]
chk("ladder 跟上计划 在计划内", lo["on_track"], True)
chk("ladder 跟上计划 在计划内话术", "在阶梯计划内" in lo["message"], True)
chk("ladder 跟上计划 不再出现'离目标还差'", "离目标还差" not in lo["message"], True)

rows_eve = [{"hour": h, "total_value": 5.0 if h in (20, 21) else 0.5} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=rows_eve, today_count=3)
chk("前瞻窗口 晚间高危", r["risk_window"], "20:00-21:00")
chk("前瞻窗口 文案被理解感", "对你来说最难" in r["risk_window_msg"], True)

r = svc.evaluate(FakeCh(), 0, 8, hour=16, hour_dist=rows_eve)
chk("前瞻窗口 今日未记录仍给窗口", r["risk_window"], "20:00-21:00")
chk("前瞻窗口 今日未记录 enabled仍False", r["enabled"], False)

rows_morn = [{"hour": h, "total_value": 5.0 if h in (8, 9) else 0.5} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=rows_morn, today_count=3)
chk("前瞻窗口 已过时段 无窗口", r["risk_window"], "")

r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=[{"hour": 20, "total_value": 5.0}], today_count=3)
chk("前瞻窗口 样本不足不给窗口", r["risk_window"], "")

rows_night_peak = [{"hour": h, "total_value": 10.0 if h in (1, 2) else 1.0} for h in range(0, 24)]
r = svc.evaluate(FakeCh(), 3, 12, hour=21, hour_dist=rows_night_peak, today_count=3)
chk("前瞻窗口 跨夜凌晨高危", r["risk_window"], "01:00-02:00")

rows_one = [{"hour": h, "total_value": 9.0 if h == 20 else 1.0} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 3, 12, hour=10, hour_dist=rows_one, today_count=3)
chk("前瞻窗口 单点峰值不显示区间重复", r["risk_window"], "20:00")

r = svc.evaluate(FakeCh("increase", "杯", "fixed"), 2, 8, hour=9, hour_dist=rows_eve, today_count=2)
chk("前瞻窗口 increase 最佳时段", "状态最好" in r["risk_window_msg"], True)

raise SystemExit(1 if fails else 0)