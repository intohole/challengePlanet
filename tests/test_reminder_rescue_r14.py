from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models.reminder import ReminderPref
from app.services.reminder_service import (
    DEFAULT_REMIND_HOUR,
    _prefers_now,
    _rescue_notify_item,
)


def _pref(hour: int, enabled: bool = True) -> ReminderPref:
    return ReminderPref(user_id="u1", remind_hour=hour, enabled=enabled)


def test_default_hour_is_20():
    assert _prefers_now(None, 20) is True
    assert _prefers_now(None, 19) is False
    assert DEFAULT_REMIND_HOUR == 20


def test_user_hour_preference():
    assert _prefers_now(_pref(9), 9) is True
    assert _prefers_now(_pref(9), 20) is False


def test_disabled_user_never_notified():
    assert _prefers_now(_pref(20, enabled=False), 20) is False


class FakeCh:
    id = 7
    title = "英语挑战"
    category = "learn"


def test_rescue_notify_item_shape():
    item = _rescue_notify_item("42", FakeCh(), 3)
    assert item["user_id"] == "42"
    assert "星轨还在" in item["title"]
    assert "3 天" in item["content"]
    assert item["link"].endswith("ch=7&rescue=1")
    assert item["data"]["rescue"] is True
    assert item["priority"] == 4
