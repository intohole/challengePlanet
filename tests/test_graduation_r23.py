"""r23 缺席中的毕业：毕业推送缺席变体 + absence gate graduated lane + gate 日志去噪。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.services.absence_service import absence_care_text, absence_revive_text
from app.services.graduation_service import (
    ABSENT_GRADUATION_GAP_DAYS,
    graduation_push_absent_text,
    graduation_push_text,
    is_graduated,
    last_checkin_date,
)
from app.services.touch_gate_service import _LAST_GATE_LOG, log_gate_decision


class FakeChallenge:
    def __init__(self, direction="decrease", task_type="counter", goal_rule="ladder",
                 target_value=25.0, unit="根", ladder_start=25.0, ladder_goal=1.0,
                 ladder_interval=1, ladder_step=1.0, start_date="2026-09-15",
                 end_date="2026-10-14", title="戒烟"):
        self.id = 60
        self.title = title
        self.direction = direction
        self.task_type = task_type
        self.goal_rule = goal_rule
        self.target_value = target_value
        self.unit = unit
        self.ladder_start = ladder_start
        self.ladder_goal = ladder_goal
        self.ladder_interval = ladder_interval
        self.ladder_step = ladder_step
        self.start_date = start_date
        self.end_date = end_date
        self.ladder_adjust = None


# ---------- 缺席中的毕业推送 ----------

def test_graduation_push_absent_text_omits_pct_and_keeps_cert():
    ch = FakeChallenge(ladder_start=12.0, ladder_goal=3.0, unit="根")
    title, body = graduation_push_absent_text(ch, avoided=18, gap_days=12, unit="根")
    assert "阶梯走完了" in title
    assert "-31%" not in body  # 缺勤期的旧 recent_avg 不许当当前降幅讲
    assert "12 根" in body and "3 根" in body
    assert "少抽了 18 根" in body
    assert "不会过期" in body


def test_graduation_push_absent_text_zero_avoided_no_empty_claim():
    ch = FakeChallenge(ladder_start=12.0, ladder_goal=3.0, unit="根")
    _, body = graduation_push_absent_text(ch, avoided=0, gap_days=10, unit="根")
    assert "少抽了" not in body
    assert "不会过期" in body


def test_graduation_push_present_text_unchanged():
    ch = FakeChallenge(title="戒烟")
    title, body = graduation_push_text(ch, avoided=120, pct=80, unit="根")
    assert "阶梯毕业" in title
    assert "-80%" in body and "毕业证书已生成" in body


def test_last_checkin_date_and_gap_threshold():
    rows = [
        {"date": "2026-10-09", "value": 7, "checkin_count": 2},
        {"date": "2026-10-16", "value": 7, "checkin_count": 2},
        {"date": "2026-10-20", "value": 0, "checkin_count": 0},
    ]
    assert last_checkin_date(rows) == "2026-10-16"
    assert last_checkin_date([{"date": "2026-10-20", "value": 0, "checkin_count": 0}]) is None
    assert ABSENT_GRADUATION_GAP_DAYS == 7


# ---------- is_graduated：纯日历判定 ----------

def test_is_graduated_calendar_based_with_shift():
    ch = FakeChallenge(ladder_start=12.0, ladder_goal=3.0, ladder_interval=2,
                       start_date="2026-10-09", end_date="2026-12-13")
    ch.ladder_adjust = None
    # 12→3 步长 1、间隔 2：无顺延 goal_day=19，即 start+18=2026-10-27
    assert is_graduated(ch, "2026-10-27") is True
    assert is_graduated(ch, "2026-10-26") is False
    ch.ladder_adjust = [{"day": 6, "shift": 2}]  # 顺延 2 天 → 10-29
    assert is_graduated(ch, "2026-10-28") is False
    assert is_graduated(ch, "2026-10-29") is True


def test_is_graduated_false_for_non_ladder():
    assert is_graduated(FakeChallenge(goal_rule="fixed"), "2026-10-29") is False
    assert is_graduated(FakeChallenge(task_type="word"), "2026-10-29") is False


# ---------- absence gate graduated lane 文案 ----------

_ABSENCE = {"absent_days": 12, "last_record_date": "2026-10-16", "last_value": 7.0,
            "cap_now": 4.0, "avoided_total": 18, "suggest_adjust": False}


def test_absence_care_graduated_variant():
    title, body = absence_care_text("戒断挑战", "根", _ABSENCE, graduated=True)
    assert "毕业" in title and "证书" in title
    assert "领走" in body
    assert "今天上限" not in body  # 毕业后不再用打卡催促语境


def test_absence_care_non_graduated_unchanged():
    title, body = absence_care_text("戒断挑战", "根", _ABSENCE)
    assert "12 天没见了" in title
    assert "今天上限 4 根" in body


def test_absence_revive_graduated_door_and_switch():
    door_t, door_b = absence_revive_text("戒断挑战", "根", _ABSENCE, "door", graduated=True)
    assert "毕业证书在等你" in door_t
    assert "最后一程" in door_b and "不急" in door_b
    sw_t, sw_b = absence_revive_text("戒断挑战", "根", _ABSENCE, "switch", graduated=True)
    assert "证书不会过期" in sw_t
    assert "不催打卡" in sw_b


def test_absence_revive_non_graduated_unchanged():
    title, _ = absence_revive_text("戒断挑战", "根", _ABSENCE, "door")
    assert title == "「戒断挑战」的门一直开着"


# ---------- gate 决策日志去噪 ----------

def test_gate_log_dedupes_repeat_decisions(caplog):
    _LAST_GATE_LOG.clear()
    with caplog.at_level("DEBUG", logger="challengePlanet.touch_gate"):
        log_gate_decision("absence", 61, "sunset", "episode_over_30d")
        for _ in range(5):
            log_gate_decision("absence", 61, "sunset", "episode_over_30d")
        log_gate_decision("absence", 63, "sunset", "episode_over_30d")  # 不同挑战各自首次
        log_gate_decision("absence", 61, "sunset", "episode_over_30d")
        log_gate_decision("rescue", 61, "sunset", "episode_over_30d")  # 不同 kind 各自首次
    infos = [r.message for r in caplog.records if r.levelname == "INFO" and "touch gate" in r.message]
    debugs = [r.message for r in caplog.records if r.levelname == "DEBUG" and "touch gate" in r.message]
    # (absence,61) 首次 1 条 + (absence,63) 首次 1 条 + (rescue,61) 首次 1 条
    assert len(infos) == 3
    assert len(debugs) >= 2  # (absence,61) 的重复决策全部降 DEBUG
    assert any("challenge 61" in m and "absence" in m for m in infos)
    _LAST_GATE_LOG.clear()
