from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.notify import get_notify_client
from nexus.logging import get_logger

from app.core.datetime_utils import now_china
from app.db.database import async_session
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.models.reminder import ReminderPref
from app.repositories.checkin_repository import CheckInRepository
from app.services.companion_service import assess_risk, companion_text
from app.services.goal_rule_service import is_cap_mode
from app.services.mercy_service import load_valid_dates
from app.services.rescue_service import assess_rescue, rescue_notify_due, rescue_text
from app.services.streak_service import calc_streak, today_str

logger = get_logger("challengePlanet.reminder")

DEFAULT_REMIND_HOUR = 20


def _reminder_content(risk: dict[str, object], total: int = 1) -> str:
    level = str(risk.get("level", "low"))
    head = f"你有 {total} 个挑战今天还没打卡，" if total > 1 else "今天还没打卡，"
    if level == "high":
        return f"{head}我注意到你最近节奏有些波动，这最容易松懈。{companion_text(risk)}"
    if level == "medium":
        return f"{head}记得留点时间完成它们。{companion_text(risk)}"
    return f"{head}别让连击断在这里！{companion_text(risk)}"


async def _get_unchecked_challenges(session: AsyncSession) -> list[Challenge]:
    today = today_str()
    result = await session.execute(
        select(Challenge).where(Challenge.status == "active")
    )
    all_active: list[Challenge] = list(result.scalars().all())
    unchecked: list[Challenge] = []
    for challenge in all_active:
        start = str(getattr(challenge, "start_date", "") or "")
        end = str(getattr(challenge, "end_date", "") or "")
        if (start and start > today) or (end and end < today):
            continue
        if is_cap_mode(challenge):
            continue
        checkin_result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge.id,
                CheckIn.date == today,
            ).limit(1)
        )
        if checkin_result.scalar_one_or_none() is None:
            unchecked.append(challenge)
    return unchecked


async def _load_prefs(session: AsyncSession) -> dict[str, ReminderPref]:
    result = await session.execute(select(ReminderPref))
    return {pref.user_id: pref for pref in result.scalars().all()}


def _prefers_now(pref: ReminderPref | None, current_hour: int) -> bool:
    if pref is not None and not pref.enabled:
        return False
    hour = pref.remind_hour if pref is not None else DEFAULT_REMIND_HOUR
    return int(hour) == current_hour


def _rescue_notify_item(
    user_id: str, challenge: Challenge, missed_days: int,
) -> dict[str, object]:
    title, body = rescue_text(challenge, missed_days)
    return {
        "user_id": str(user_id),
        "title": title,
        "content": body,
        "type": "task",
        "priority": 4,
        "app_id": "challengePlanet",
        "channels": ["in_app", "email"],
        "link": f"/challengePlanet/?ch={challenge.id}&rescue=1",
        "data": {"challenge_id": challenge.id, "missed_days": missed_days, "rescue": True},
    }


async def send_checkin_reminders(current_hour: int | None = None) -> None:
    try:
        current = current_hour if current_hour is not None else now_china().hour
        async with async_session() as session:
            unchecked = await _get_unchecked_challenges(session)
            if not unchecked:
                logger.info("No unchecked challenges found, skipping reminders.")
                return
            prefs = await _load_prefs(session)
            grouped: dict[str, list[Challenge]] = {}
            for challenge in unchecked:
                pref = prefs.get(str(challenge.user_id))
                if _prefers_now(pref, current):
                    grouped.setdefault(str(challenge.user_id), []).append(challenge)
            if not grouped:
                logger.info("No users preferring hour=%s, skipping.", current)
                return
            logger.info("Sending reminders to %d users at hour=%s...", len(grouped), current)
            client = get_notify_client()
            checkins_repo = CheckInRepository()
            items: list[dict[str, object]] = []
            rescued_ids: set[int] = set()
            for user_id, challenges in grouped.items():
                rescue_items: list[tuple[Challenge, dict[str, object]]] = []
                for challenge in challenges:
                    valid = await load_valid_dates(session, challenge.id)
                    signal = assess_rescue(challenge, valid, today_str(), today_checked=False)
                    if signal and rescue_notify_due(int(signal["missed_days"]), today_str()):
                        rescue_items.append((challenge, signal))
                for challenge, signal in rescue_items:
                    rescued_ids.add(challenge.id)
                    items.append(_rescue_notify_item(user_id, challenge, int(signal["missed_days"])))
                normal = [c for c in challenges if c.id not in rescued_ids]
                if not normal:
                    continue
                representative = normal[0]
                checkins = await checkins_repo.get_by_challenge(session, representative.id)
                valid = await load_valid_dates(session, representative.id)
                streak = calc_streak(valid, today_str())
                risk = assess_risk(checkins, streak, today_str())
                content = _reminder_content(risk, len(normal))
                if len(normal) > 1:
                    title = f"{len(normal)} 个挑战待打卡"
                else:
                    title = f"「{representative.title}」打卡提醒"
                priority = 4 if risk["level"] == "high" else 3
                items.append(
                    {
                        "user_id": user_id,
                        "title": title,
                        "content": content,
                        "type": "task",
                        "priority": priority,
                        "app_id": "challengePlanet",
                        "channels": ["in_app", "email"],
                        "link": "/challengePlanet/",
                        "data": {"challenge_count": len(normal)},
                    }
                )
            if items:
                await client.send_many(items)
            logger.info(
                "Check-in reminders processed: %d items (%d rescue) for %d users.",
                len(items), len(rescued_ids), len(grouped),
            )
    except Exception as e:
        logger.error("Check-in reminder task failed: %s", e)
