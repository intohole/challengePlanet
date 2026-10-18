from __future__ import annotations

import json
from datetime import date

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.checkin_repository import InsightRepository
from app.services.goal_rule_service import is_cap_mode
from app.services.streak_service import (
    day_number_of,
    shift_date,
    today_str,
)

logger = get_logger("challengePlanet.rescue")

RESCUE_CARE_INSIGHT = "rescue_care"

REPAIR_WINDOW_DAYS = 1
RESCUE_MAX_MISSED = 14
LEVEL_SLIP = "slip"
LEVEL_RESCUE = "rescue"
LEVEL_DEEP = "deep"

RESCUE_FIRST_NOTIFY_DAY = 3
_DEEP_NOTIFY_WEEKDAYS = (1, 4)


def rescue_notify_due(missed_days: int, today: str) -> bool:
    """催促通道首发门槛+降频：断 1-2 天静默（提醒/救援卡在 app 内等他），≥3 天首条，4-6 天隔日，≥7 天每周二/五。

    断 1-2 天是打卡类挑战的正常波动（真实用户行为就是积攒几天一次补记），
    「星轨还在」生产实锤三轮 0 已读——推送留给真正的失踪（对齐 cap 侧 absence day3 首发节奏）；
    救援动线本身（App 内救援卡）不受影响，只节流推送通道。
    """
    if missed_days < RESCUE_FIRST_NOTIFY_DAY:
        return False
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


async def mark_rescue_sent(
    session: AsyncSession, challenge_id: int, user_id: str, missed_days: int,
) -> None:
    """先发送后落痕（status=='sent' 才记），失败/被抑制不落痕=次日 job 自然重试。"""
    await InsightRepository().create(session, {
        "challenge_id": challenge_id,
        "user_id": user_id,
        "insight_type": RESCUE_CARE_INSIGHT,
        "content": json.dumps({
            "date": today_str(),
            "missed_days": int(missed_days),
        }, ensure_ascii=False),
    })


async def rescue_sent_today(session: AsyncSession, challenge_id: int) -> bool:
    """当天已发过催促（同日补跑 job 幂等）：rescue_care 落痕的 date==今天。"""
    row = await InsightRepository().get_by_type(session, challenge_id, RESCUE_CARE_INSIGHT)
    if row is None:
        return False
    try:
        payload = json.loads(str(row.content or "{}"))
    except ValueError:
        return False
    return str(payload.get("date", "")) == today_str()


