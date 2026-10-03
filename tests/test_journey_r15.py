from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.journey_service import (
    compute_journey,
    cumulative_avoided,
    journey_prompt_line,
    ladder_stage_info,
    milestone_rows,
    reduction_pct,
    recent_average,
    trailing_guard_days,
)


class FakeChallenge:
    def __init__(self, direction="decrease", task_type="counter", goal_rule="ladder",
                 target_value=25.0, unit="根", ladder_start=25.0, ladder_goal=1.0,
                 ladder_interval=1, ladder_step=1.0):
        self.id = 60
        self.title = "戒烟"
        self.direction = direction
        self.task_type = task_type
        self.goal_rule = goal_rule
        self.target_value = target_value
        self.unit = unit
        self.ladder_start = ladder_start
        self.ladder_goal = ladder_goal
        self.ladder_interval = ladder_interval
        self.ladder_step = ladder_step


def _rows(pairs):
    return [{"date": d, "value": v, "checkin_count": 1} for d, v in pairs]


def test_avoided_counts_only_record_days():
    rows = _rows([("2026-09-29", 3.0), ("2026-09-30", 11.0), ("2026-10-01", 4.0)])
    avoided, marks = cumulative_avoided(rows, 25.0)
    assert avoided == (22 + 14 + 21)
    assert "avoided_50" in marks and "avoided_100" not in marks


def test_avoided_skips_gap_days_and_clamps():
    rows = _rows([("2026-09-29", 30.0), ("2026-09-30", 20.0)])
    avoided, _ = cumulative_avoided(rows, 25.0)
    assert avoided == 5


def test_reduction_pct_bounds():
    assert reduction_pct(25.0, 4.0) == 84
    assert reduction_pct(25.0, 30.0) == 0
    assert reduction_pct(0, 4.0) == 0


def test_recent_average_prefers_last7_when_enough_days():
    rows = _rows([(f"2026-09-{d:02d}", float(d)) for d in range(1, 11)])
    avg = recent_average(rows)
    assert avg == round(sum(range(4, 11)) / 7, 2)


def test_ladder_stage_info_25_to_1():
    ch = FakeChallenge()
    info = ladder_stage_info(ch, 1)
    assert info == {"stage": 1, "total_stages": 25}
    info18 = ladder_stage_info(ch, 18)
    assert info18["stage"] == 18
    info30 = ladder_stage_info(ch, 40)
    assert info30 == {"stage": 25, "total_stages": 25}


def test_guard_days_trailing():
    ch = FakeChallenge()
    rows = _rows([
        ("2026-09-28", 4.0), ("2026-09-29", 4.0), ("2026-09-30", 20.0),
        ("2026-10-01", 4.0), ("2026-10-02", 4.0),
    ])
    streak = trailing_guard_days(rows, ch, date(2026, 9, 15))
    assert streak == 2


def test_compute_journey_reduction_full():
    ch = FakeChallenge()
    rows = _rows([("2026-09-29", 3.0), ("2026-09-30", 11.0), ("2026-10-01", 4.0),
                  ("2026-10-02", 4.0), ("2026-10-03", 4.0)])
    j = compute_journey(ch, rows, 19, date(2026, 9, 15), date(2026, 10, 3))
    assert j["mode"] == "reduction"
    assert j["baseline"] == 25.0
    assert j["cigarettes_avoided"] == 22 + 14 + 21 + 21 + 21
    assert j["money_saved"] == round(j["cigarettes_avoided"] * 0.9)
    assert j["ladder_stage"] == 19 and j["ladder_total_stages"] == 25
    assert j["days_to_goal"] == 6
    assert j["goal_date"] == "2026-10-09"
    reached = [m["key"] for m in j["milestones"] if m["reached"]]
    assert "avoided_50" in reached and "avoided_100" not in reached
    assert "ladder_half" in reached
    health = j["health"]
    assert health["anchor_date"] == "2026-10-09"
    assert all(not m["reached"] for m in health["milestones"])
    assert "疾控" in health["source_note"] or "癌症协会" in health["source_note"]


def test_compute_journey_quit_binary_mode():
    ch = FakeChallenge(task_type="binary", goal_rule="fixed", target_value=1.0, unit="次")
    rows = _rows([("2026-10-01", 0.0), ("2026-10-02", 0.0)])
    j = compute_journey(ch, rows, 3, date(2026, 10, 1), date(2026, 10, 3))
    assert j["mode"] == "quit"
    assert j["quit_days"] == 2
    assert "cigarettes_avoided" not in j
    health = j["health"]
    assert health["anchor_date"] == "2026-10-01"
    assert health["milestones"][0]["reached"] is True
    assert health["milestones"][1]["reached"] is True
    assert health["milestones"][2]["reached"] is False


def test_compute_journey_none_for_increase():
    ch = FakeChallenge(direction="increase", goal_rule="fixed", ladder_start=0, ladder_goal=0)
    assert compute_journey(ch, [], 1, date(2026, 10, 1), date(2026, 10, 3)) is None


def test_milestone_rows_half_semantics():
    rows = milestone_rows(set(), {"stage": 13, "total_stages": 25}, 0)
    half = next(m for m in rows if m["key"] == "ladder_half")
    assert half["reached"] is True
    rows_early = milestone_rows(set(), {"stage": 12, "total_stages": 25}, 0)
    assert next(m for m in rows_early if m["key"] == "ladder_half")["reached"] is False
    rows2 = milestone_rows({"avoided_50"}, {"stage": 3, "total_stages": 25}, 6)
    keys = {m["key"]: m["reached"] for m in rows2}
    assert keys["avoided_50"] is True and keys["avoided_100"] is False
    assert keys["ladder_half"] is False
    guard = next(m for m in rows2 if m["key"] == "guard_7")
    assert guard["reached"] is False


def test_journey_prompt_line_reduction_and_quit():
    ch = FakeChallenge()
    rows = _rows([("2026-10-01", 4.0), ("2026-10-02", 4.0)])
    j = compute_journey(ch, rows, 18, date(2026, 9, 15), date(2026, 10, 3))
    line = journey_prompt_line(j)
    assert "少抽" in line and "阶梯第" in line
    ch2 = FakeChallenge(task_type="binary", goal_rule="fixed", target_value=1.0)
    j2 = compute_journey(ch2, _rows([("2026-10-01", 0.0)]), 1, date(2026, 10, 1), date(2026, 10, 3))
    line2 = journey_prompt_line(j2)
    assert "戒断" in line2
    assert journey_prompt_line(None) == ""
