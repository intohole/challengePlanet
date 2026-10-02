from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rescue_service import (
    LEVEL_DEEP,
    LEVEL_RESCUE,
    LEVEL_SLIP,
    assess_rescue,
    rescue_text,
)
from app.services.streak_service import shift_date, today_str


class FakeChallenge:
    def __init__(
        self,
        start: str,
        end: str,
        category: str = "learn",
        direction: str = "increase",
        goal_rule: str = "fixed",
        ladder: bool = False,
    ):
        self.id = 1
        self.title = "英语挑战"
        self.category = category
        self.start_date = start
        self.end_date = end
        self.direction = direction
        self.goal_rule = goal_rule
        self.goal_type = "ladder" if ladder else "hard"


def _mk(today: str) -> tuple[str, str, str]:
    """挑战期覆盖断档窗口：start = today-30, end = today+30。"""
    return shift_date(today, -30), shift_date(today, 30), today


def test_yesterday_broken_is_slip():
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    before_yesterday = shift_date(today, -2)
    signal = assess_rescue(ch, {before_yesterday}, today, today_checked=False)
    assert signal["missed_days"] == 1
    assert signal["rescue_level"] == LEVEL_SLIP
    assert signal["can_repair"] is True


def test_three_days_broken_is_rescue():
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    checked = {shift_date(today, -4)}
    signal = assess_rescue(ch, checked, today, today_checked=False)
    assert signal["missed_days"] == 3
    assert signal["rescue_level"] == LEVEL_RESCUE
    assert signal["can_repair"] is False


def test_deep_level_after_four_days():
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    checked = {shift_date(today, -9), shift_date(today, -8)}
    signal = assess_rescue(ch, checked, today, today_checked=False)
    assert signal["missed_days"] == 7
    assert signal["rescue_level"] == LEVEL_DEEP


def test_healthy_challenge_no_signal():
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    assert assess_rescue(ch, {shift_date(today, -1)}, today, today_checked=False) == {}
    assert assess_rescue(ch, {today, shift_date(today, -1)}, today, today_checked=True) == {}


def test_never_started_no_signal():
    """从没打过卡的挑战不属于「断档」，不触发救援。"""
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    assert assess_rescue(ch, set(), today, today_checked=False) == {}


def test_cap_mode_excluded():
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end, category="quit", direction="decrease")
    ch.task_type = "counter"
    assert assess_rescue(ch, {shift_date(today, -5)}, today, today_checked=False) == {}


def test_out_of_period_excluded():
    today = today_str()
    ch = FakeChallenge(shift_date(today, -3), shift_date(today, -1))
    assert assess_rescue(ch, {shift_date(today, -2)}, today, today_checked=False) == {}


def test_today_counted_after_repair_action():
    """freeze/repair/shield 动作日计入 valid_dates 后视为健康。"""
    start, end, today = _mk(today_str())
    ch = FakeChallenge(start, end)
    valid = {shift_date(today, -1)}
    assert assess_rescue(ch, valid, today, today_checked=False) == {}


def test_rescue_text_variants():
    start, end, today = _mk(today_str())
    quit_ch = FakeChallenge(start, end, category="quit")
    learn_ch = FakeChallenge(start, end)
    title, body = rescue_text(quit_ch, 5)
    assert "星轨还在" in title and "重新开始" in body
    title2, body2 = rescue_text(learn_ch, 1)
    assert "补回来" in body2
    title3, body3 = rescue_text(learn_ch, 6)
    assert "不代表失败" in body3
