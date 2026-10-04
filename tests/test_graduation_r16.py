from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.graduation_service import (
    graduation_block,
    graduation_goal_day,
    graduation_push_text,
    milestone_push_rows,
    milestone_push_text,
)
from app.services.journey_service import compute_journey
from app.services.rescue_service import rescue_notify_due


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


def _rows(pairs):
    return [{"date": d, "value": v, "checkin_count": 1} for d, v in pairs]


def test_goal_day_ladder_25_to_1():
    ch = FakeChallenge()
    assert graduation_goal_day(ch) == 25


def test_goal_day_none_for_non_ladder_and_non_cap():
    assert graduation_goal_day(FakeChallenge(goal_rule="fixed")) is None
    assert graduation_goal_day(FakeChallenge(task_type="word")) is None
    assert graduation_goal_day(FakeChallenge(ladder_start=0)) is None
    assert graduation_goal_day(FakeChallenge(ladder_start=1, ladder_goal=1)) is None


def test_block_states_on_track_approaching_graduated():
    ch = FakeChallenge()
    start = date(2026, 9, 15)
    on_track = graduation_block(ch, 20, start, date(2026, 10, 4))
    assert on_track["state"] == "on_track"
    assert on_track["days_to_graduation"] == 5
    approaching = graduation_block(ch, 22, start, date(2026, 10, 6))
    assert approaching["state"] == "approaching"
    assert approaching["days_to_graduation"] == 3
    grad = graduation_block(ch, 25, start, date(2026, 10, 9))
    assert grad["state"] == "graduated"
    assert grad["graduation_date"] == "2026-10-09"
    assert grad["final_cap"] == 1.0


def test_block_keep_days_window():
    ch = FakeChallenge()
    grad = graduation_block(ch, 26, date(2026, 9, 15), date(2026, 10, 10))
    assert grad["state"] == "graduated"
    assert grad["keep_day"] == 2
    assert grad["keep_days_total"] == 6


def test_milestone_rows_only_new_crossings():
    rows = _rows([("2026-10-01", 25.0), ("2026-10-02", 25.0)])
    assert milestone_push_rows(rows, 25.0, (50, 100)) == []
    rows_all = _rows([("2026-10-01", 4.0), ("2026-10-02", 4.0), ("2026-10-03", 4.0)])
    crossed = milestone_push_rows(rows_all, 25.0, (50, 100))
    assert crossed == [50]
    legacy = _rows([("2026-10-01", 1.0), ("2026-10-02", 1.0), ("2026-10-03", 1.0), ("2026-10-04", 1.0)])
    assert milestone_push_rows(legacy, 25.0, (50, 100)) == []


def test_milestone_zero_day_counts():
    rows = _rows([("2026-10-01", 4.0), ("2026-10-03", 4.0), ("2026-10-05", 0.0)])
    crossed = milestone_push_rows(rows, 25.0, (50, 100))
    assert 50 in crossed


def test_journey_graduation_block_and_health_anchor_switch():
    ch = FakeChallenge()
    start = date(2026, 9, 15)
    before = compute_journey(ch, _rows([("2026-10-01", 4.0)]), 20, start, date(2026, 10, 4))
    assert before["graduation"]["state"] == "on_track"
    assert before["health"]["anchor_label"] == "按你的阶梯计划到达终点后"
    assert before["health"]["anchor_date"] == "2026-10-09"
    after = compute_journey(ch, _rows([("2026-10-01", 4.0), ("2026-10-09", 1.0)]), 25, start, date(2026, 10, 9))
    assert after["graduation"]["state"] == "graduated"
    assert after["health"]["anchor_label"] == "从你阶梯毕业那天起"
    assert after["health"]["anchor_date"] == "2026-10-09"
    hr = after["health"]["milestones"][0]
    assert hr["reached"] is True


def test_journey_non_ladder_has_no_graduation():
    ch = FakeChallenge(goal_rule="fixed", task_type="counter")
    j = compute_journey(ch, _rows([("2026-10-01", 4.0)]), 5, date(2026, 9, 15), date(2026, 10, 4))
    assert j is not None and "graduation" not in j


def test_push_texts():
    title, body = milestone_push_text("根", 100)
    assert "100" in title and "少抽" in body
    ch = FakeChallenge()
    gtitle, gbody = graduation_push_text(ch, 250, 96, "根")
    assert "阶梯毕业" in gtitle
    assert "25" in gbody and "250" in gbody and "96" in gbody


def test_rescue_notify_due_throttle():
    for m in (1, 2, 3):
        assert rescue_notify_due(m, "2026-10-05") is True
    assert rescue_notify_due(4, "2026-10-05") is False
    assert rescue_notify_due(4, "2026-10-06") is True
    assert rescue_notify_due(9, "2026-10-06") is True
    assert rescue_notify_due(9, "2026-10-07") is False
    assert rescue_notify_due(12, "2026-10-09") is True
