from __future__ import annotations

import sys

sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

from app.services.nudge_service import NudgeService


class FakeCh:
    def __init__(self, direction="decrease", unit="根", goal_rule="ladder",
                 ladder_goal=0.0, ladder_start=0.0, duration_days=30):
        self.direction = direction
        self.unit = unit
        self.goal_rule = goal_rule
        self.ladder_goal = ladder_goal
        self.ladder_start = ladder_start
        self.duration_days = duration_days


svc = NudgeService()
fails = 0


def chk(name, got, want):
    global fails
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "=>", got)
    if not ok:
        fails += 1


r = svc.evaluate(FakeCh(), 4, 5, hour=10)
chk("decrease 10点已4根 enabled", r["enabled"], True)
chk("decrease 10点已4根 projected", r["projected"], 18.0)
chk("decrease 10点已4根 risk=1", r["risk_level"], 1)
chk("decrease 10点已4根 触顶11:00", r["touch_at"], "11:00")
chk("decrease 10点已4根 剩余弹性1h", r["remaining_hours"], 1.0)
chk("decrease 10点已4根 剩余配额1", r["remaining_units"], 1.0)
chk("decrease 10点已4根 nudge_level=1", r["nudge_level"], 1)

r = svc.evaluate(FakeCh(), 6, 5, hour=15)
chk("decrease 已超限 risk=2", r["risk_level"], 2)
chk("decrease 已超限 话术", r["coach_nudge"], "今天已6根，超过目标了。身体比目标重要，先喝口水停一停")

r = svc.evaluate(FakeCh(), 5, 5, hour=15)
chk("decrease 到顶 risk=2", r["risk_level"], 2)
chk("decrease 到顶 话术", r["coach_nudge"], "今天已5/5根，到顶了。先停一停，下一次留到更需要的时刻")

r = svc.evaluate(FakeCh(), 2, 20, hour=14)
chk("decrease 安全 risk=0", r["risk_level"], 0)
chk("decrease 安全 无话术", r["coach_nudge"], "")

r = svc.evaluate(FakeCh(), 0, 8, hour=20)
chk("decrease 无记录 disabled", r["enabled"], False)

rows = [{"hour": h, "total_value": 2.0 if h in (8, 9, 10) else 0.3} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 4, 5, hour=11, hour_dist=rows)
chk("decrease 时段加权 projected>5", r["projected"] > 5.0, True)
chk("decrease 时段加权 risk=1", r["risk_level"], 1)

rows_sparse = [{"hour": 20, "total_value": 60.0, "checkin_count": 10},
               {"hour": 21, "total_value": 40.0, "checkin_count": 6},
               {"hour": 22, "total_value": 30.0, "checkin_count": 5}]
r = svc.evaluate(FakeCh(), 2, 5, hour=10, hour_dist=rows_sparse)
chk("decrease 稀疏分布 不极端放大", r["projected"] <= 20, True)
chk("decrease 稀疏分布 上午10点预计9根", round(r["projected"]), 9)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 2, 5, hour=21)
chk("increase 20点后未达标 level", r["nudge_level"], 1)
chk("increase 20点后话术", r["coach_nudge"], "今天还差3组，现在补上，今晚睡得踏实")

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 1, 5, hour=18)
chk("increase 17点未过半 level", r["nudge_level"], 1)
chk("increase 17点未过半话术", r["coach_nudge"], "今天进度还没过半，还差4组，趁现在抓紧就达标了")

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 5, 5, hour=21)
chk("increase 已达标不提醒", r["nudge_level"], 0)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 7, 5, hour=14, is_soft_exceeded=True)
chk("increase soft超限不提醒", r["nudge_level"], 0)

rows_wd = [{"hour": 14, "total_value": 3.0, "checkin_count": 3},
           {"hour": 15, "total_value": 3.0, "checkin_count": 3},
           {"hour": 16, "total_value": 2.0, "checkin_count": 2},
           {"hour": 9, "total_value": 1.0, "checkin_count": 1}]
r = svc.evaluate(FakeCh(), 4, 5, hour=10, hour_dist=rows, weekday_dist=rows_wd)
chk("decrease 星期加权 basis", r["basis"], "按你最近两周的同时段节奏")
chk("decrease 星期加权 confidence>0", r["confidence"] > 0, True)
chk("decrease 星期加权 有区间", r["projected_high"] > r["projected_low"], True)

r = svc.evaluate(FakeCh(), 4, 5, hour=10, hour_dist=rows)
chk("decrease 全量分布 basis", r["basis"], "按你最近两周的节奏")
chk("decrease 全量分布 高把握", r["confidence_label"], "高")
chk("decrease 全量分布 预计区间包含", r["projected_low"] <= r["projected"] <= r["projected_high"], True)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 3, 5, hour=12)
chk("increase 12点已3组 达标时刻", r["reach_at"], "16:00")
chk("increase 12点已3组 今日预计", r["projected"], 9.0)

r = svc.evaluate(FakeCh("increase", "组", "fixed"), 1, 20, hour=21)
chk("increase 21点进度太慢 无达标时刻", r["reach_at"], "")
chk("increase 21点进度太慢 nudge=1", r["nudge_level"], 1)

ch = FakeCh(ladder_goal=5.0, duration_days=45)
r = svc.evaluate(ch, 4, 8, hour=10, hour_dist=rows, day_number=15, recent_avg=6.0)
lo = r["ladder_outlook"]
chk("ladder 终点预测 未达目标", lo["on_track"], False)
chk("ladder 终点预测 结束值", lo["projected_end"], 6.0)
chk("ladder 终点预测 剩余天数", lo["remaining_days"], 30)
chk("ladder 终点预测 话术含差距", "还差" in lo["message"], True)
chk("ladder 终点预测 无多余小数", ".0" not in lo["message"], True)

ch2 = FakeCh(ladder_goal=8.0, duration_days=45)
r = svc.evaluate(ch2, 4, 8, hour=10, hour_dist=rows, day_number=15, recent_avg=6.0)
chk("ladder 终点预测 达标", r["ladder_outlook"]["on_track"], True)

fc = svc.evaluate(FakeCh(), 4, 5, hour=10, hour_dist=rows)
fc2 = svc.apply_bias(fc, 2.0)
chk("bias 修正 预计上调", fc2["projected"], 11.1)
chk("bias 修正 标记", fc2["calibrated"], True)
fc3 = svc.apply_bias(fc, None)
chk("bias 空 不变", fc3["projected"], fc["projected"])
fc4 = svc.apply_bias(svc.evaluate(FakeCh(), 0, 5, hour=10), 2.0)
chk("bias 未启用 不变", fc4["enabled"], False)

rows_eve = [{"hour": h, "total_value": 5.0 if h in (20, 21) else 0.5} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=rows_eve)
chk("前瞻窗口 晚间高危", r["risk_window"], "20:00-21:00")
chk("前瞻窗口 文案被理解感", "对你来说最难" in r["risk_window_msg"], True)

r = svc.evaluate(FakeCh(), 0, 8, hour=16, hour_dist=rows_eve)
chk("前瞻窗口 今日未记录仍给窗口", r["risk_window"], "20:00-21:00")
chk("前瞻窗口 今日未记录 enabled仍False", r["enabled"], False)

rows_morn = [{"hour": h, "total_value": 5.0 if h in (8, 9) else 0.5} for h in range(6, 24)]
r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=rows_morn)
chk("前瞻窗口 已过时段 无窗口", r["risk_window"], "")

r = svc.evaluate(FakeCh(), 3, 8, hour=16, hour_dist=[{"hour": 20, "total_value": 5.0}])
chk("前瞻窗口 样本不足不给窗口", r["risk_window"], "")

r = svc.evaluate(FakeCh("increase", "杯", "fixed"), 2, 8, hour=9, hour_dist=rows_eve)
chk("前瞻窗口 increase 最佳时段", "状态最好" in r["risk_window_msg"], True)

raise SystemExit(1 if fails else 0)
