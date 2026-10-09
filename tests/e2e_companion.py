import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.companion_service import assess_risk, companion_meta, companion_text

passed = []
failed = []


def check(name, cond, extra=""):
    if cond:
        passed.append(name)
        print("PASS", name, extra)
    else:
        failed.append(name)
        print("FAIL", name, extra)


def ck(date, mood="", pct=100):
    return SimpleNamespace(date=date, mood=mood, completion_pct=pct)


today = "2026-08-20"

# 场景1: 空打卡(未开始)
r = assess_risk([], 0, today)
check("空打卡 low 且无原因", r["level"] == "low" and not r["reasons"] and r["score"] == 0)

# 场景2: 刚断签 streak=0, 适应期, 心情bad → high
checkins = [
    ck("2026-08-16", "good"), ck("2026-08-17", "bad"),
    ck("2026-08-18", "normal"), ck("2026-08-19", "normal"),
]
r = assess_risk(checkins, 0, today)
check("断签+适应+bad → high", r["level"] == "high", "score=%d reasons=%s" % (r["score"], r["reasons"]))
check("bad 心情触发微行动", "放低要求" in r["micro_action"])

# 场景3: 中等 - 稳定期streak=5，无bad无gap，但最近未达标
checkins2 = [ck("2026-08-18", pct=60), ck("2026-08-19", pct=60)]
r2 = assess_risk(checkins2, 5, today)
check("未达标→medium以上", r2["level"] in ("medium", "high"), "score=%d" % r2["score"])
check("打卡少→适应期", r2["phase"] == "adaptation")

# 场景4: 长期稳定无风险 → low
checkins3 = [ck(d) for d in ["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17", "2026-08-18", "2026-08-19"]]
r3 = assess_risk(checkins3, 6, today)
check("稳定期连续6天 → low", r3["level"] == "low", "score=%d" % r3["score"])

# 场景5: companion_text 有内容且与原因呼应
r = assess_risk(checkins, 0, today)
txt = companion_text(r)
check("companion_text 非空", bool(txt.strip()) and "我" in txt)
check("companion_text 引用原因", any("中断" in txt for _ in [0]) or "重启" in txt)

# 场景6: companion_text 兜底文案
r4 = assess_risk([], 0, today)
check("无风险兜底文案", "稳住" in companion_text(r4) or "打卡" in companion_text(r4))

# 场景7: companion_meta 提取字段
state = {
    "challenge_id": 1, "completed_days": 3, "streak": 2, "phase": "adaptation",
    "risk": {"level": "medium", "score": 55}, "ladder_progress_pct": 60,
}
meta = companion_meta(state)
check("meta 含全部字段", all(k in meta for k in ("challenge_id", "completed_days", "streak", "phase", "risk_level", "risk_score", "ladder_progress_pct")))
check("meta 风险等级映射", meta["risk_level"] == "medium" and meta["risk_score"] == 55)
check("meta 阶梯进度", meta["ladder_progress_pct"] == 60)

# 场景8: companion_meta 无风险时兜底 low
meta2 = companion_meta({"challenge_id": 2, "completed_days": 0, "streak": 0, "phase": "adaptation", "ladder_progress_pct": None})
check("meta 无风险兜底 low", meta2["risk_level"] == "low" and meta2["risk_score"] == 0)
check("meta 无阶梯为 null", meta2["ladder_progress_pct"] is None)

print("\n== 风险引擎 通过 %d / 失败 %d ==" % (len(passed), len(failed)))
if failed:
    sys.exit(1)