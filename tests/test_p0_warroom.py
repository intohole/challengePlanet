from __future__ import annotations

import pytest

from app.services.goal_rule_service import (
    ensure_ladder_direction,
    ladder_progress_pct,
)
from app.services.streak_service import shift_date, today_str


class _Ch:
    def __init__(self, direction: str) -> None:
        self.direction = direction
        self.goal_rule = "ladder"
        self.ladder_start = 2.0
        self.ladder_goal = 5.0
        self.ladder_interval = 2
        self.ladder_step = 1.0
        self.ladder_adjust = None
        self.ladder_restart = None
        self.start_date = shift_date(today_str(), -10)
        self.target_value = 2.0


def test_ladder_progress_pct_increase_returns_float() -> None:
    ch = _Ch("increase")
    pct = ladder_progress_pct(ch, 1)
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_ladder_progress_pct_decrease_still_works() -> None:
    ch = _Ch("decrease")
    ch.ladder_goal = 0.0
    pct = ladder_progress_pct(ch, 1)
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_ensure_ladder_direction_rejects_increase() -> None:
    with pytest.raises(ValueError):
        ensure_ladder_direction("increase", "ladder")


def test_ensure_ladder_direction_allows_decrease() -> None:
    ensure_ladder_direction("decrease", "ladder")
    ensure_ladder_direction("increase", "fixed")
    ensure_ladder_direction("", "")
