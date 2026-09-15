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


chk("decrease 超限 ladder", svc.evaluate(FakeCh(goal_rule="ladder"), 6, 5, hour=15), (2, "今天已6根，量到顶了。先歇一歇，明天配额会自动更低"))
chk("decrease 超限 fixed", svc.evaluate(FakeCh("decrease", "根", "fixed"), 4, 3, hour=15), (2, "今天已4根，超过目标了。先喝口水停一停，身体比目标重要"))
chk("decrease 逼近 剩1根", svc.evaluate(FakeCh(), 4, 5, hour=11), (1, "今天还剩1根的量，留到更需要的时刻"))
chk("decrease 逼近 剩2根", svc.evaluate(FakeCh(), 3, 5, hour=11), (1, "今天还剩2根的量，留到更需要的时刻"))
chk("decrease 节奏外推超限", svc.evaluate(FakeCh(), 12, 15, hour=18), (1, "按现在的节奏，今天会到18根。让下一根的间隔再长一点"))
chk("decrease 正常无提醒", svc.evaluate(FakeCh(), 2, 20, hour=14), (0, ""))
chk("decrease 进度0不提醒", svc.evaluate(FakeCh(), 0, 8, hour=20), (0, ""))
chk("increase 20点后未达标", svc.evaluate(FakeCh("increase", "组", "fixed"), 2, 5, hour=21), (1, "今天还差3组，现在补上，今晚睡得踏实"))
chk("increase 17点未过半", svc.evaluate(FakeCh("increase", "组", "fixed"), 1, 5, hour=18), (1, "今天进度还没过半，还差4组，趁现在抓紧就达标了"))
chk("increase 已达标不提醒", svc.evaluate(FakeCh("increase", "组", "fixed"), 5, 5, hour=21), (0, ""))
chk("increase 白天正常不提醒", svc.evaluate(FakeCh("increase", "组", "fixed"), 2, 5, hour=14), (0, ""))
chk("increase soft超限不提醒", svc.evaluate(FakeCh("increase", "组", "fixed"), 7, 5, hour=14, is_soft_exceeded=True), (0, ""))

raise SystemExit(1 if fails else 0)