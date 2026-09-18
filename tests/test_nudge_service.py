from __future__ import annotations

import sys

sys.path.insert(0, "/Users/intoblack/remoteWork/challengePlanet")

from app.services.nudge_service import NudgeService


class FakeCh:
    def __init__(self, direction="decrease", unit="根", goal_rule="ladder"):
        self.direction = direction
        self.unit = unit
        self.goal_rule = goal_rule


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

raise SystemExit(1 if fails else 0)
