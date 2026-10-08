from __future__ import annotations

from datetime import date

from nexus.logging import get_logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.goal_rule_service import is_cap_mode
from app.services.streak_service import (
    day_number_of,
    list_missed_dates,
    shift_date,
    today_str,
)

logger = get_logger("challengePlanet.rescue")

REPAIR_WINDOW_DAYS = 1
RESCUE_MAX_MISSED = 14
LEVEL_SLIP = "slip"
LEVEL_RESCUE = "rescue"
LEVEL_DEEP = "deep"

_DEEP_NOTIFY_WEEKDAYS = (1, 4)


def rescue_notify_due(missed_days: int, today: str) -> bool:
    """深断档催促降频：≤3 天每天提醒，4-6 天隔日，≥7 天每周二/五。

    断档越久，「每天被同一句提醒敲打」的催促效应越差于低频触达；
    救援动线本身（App 内救援卡）不受影响，只节流推送通道。
    """
    if missed_days <= 3:
        return True
    if missed_days <= 6:
        return int(today.replace("-", "")) % 2 == 0
    try:
        return date.fromisoformat(today).weekday() in _DEEP_NOTIFY_WEEKDAYS
    except ValueError:
        return True


_LEVEL_BY_MISSED = (
    (REPAIR_WINDOW_DAYS, LEVEL_SLIP),
    (3, LEVEL_RESCUE),
)


def assess_rescue(
    challenge: Challenge,
    valid_dates: set[str],
    today: str,
    today_checked: bool,
) -> dict[str, object]:
    start = str(getattr(challenge, "start_date", "") or "")
    end = str(getattr(challenge, "end_date", "") or "")
    if not start or not end:
        return {}
    if today < start or today > end:
        return {}
    if is_cap_mode(challenge):
        return {}
    yesterday = shift_date(today, -1)
    if yesterday in valid_dates or yesterday < start:
        return {}
    missed_days = 0
    cursor = yesterday
    while cursor >= start and cursor not in valid_dates:
        missed_days += 1
        cursor = shift_date(cursor, -1)
    completed_before = sum(1 for d in valid_dates if d < yesterday)
    if completed_before <= 0:
        return {}
    level = LEVEL_DEEP
    for threshold, name in _LEVEL_BY_MISSED:
        if missed_days <= threshold:
            level = name
            break
    return {
        "missed_days": missed_days,
        "rescue_level": level,
        "can_repair": missed_days == REPAIR_WINDOW_DAYS,
        "mend_date": yesterday,
        "last_checked_date": shift_date(yesterday, -missed_days),
        "day_number": day_number_of(start, today),
    }


def rescue_text(challenge: Challenge, missed_days: int) -> tuple[str, str]:
    title = str(challenge.title or "挑战")
    category = str(getattr(challenge, "category", "") or "")
    is_quit = category == "quit"
    if missed_days <= 1:
        body = "断了 1 天而已，昨天可以一键补回来，节奏马上恢复。"
    elif missed_days <= 3:
        body = f"断了 {missed_days} 天，别灰心——完成过的 {missed_days} 天都还在，先补一天，星轨就重新亮起来。"
    else:
        body = f"断了 {missed_days} 天，这不代表失败。回头看看当初为什么出发，我们把节奏调回来。"
    if is_quit:
        body += "记得：一次没记录不等于前功尽弃，每一天都可以重新开始。"
    return f"「{title}」的星轨还在", body


