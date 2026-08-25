from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.notify import get_notify_client
from nexus.logging import get_logger

from app.db.database import async_session
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.repositories.checkin_repository import CheckInRepository
from app.services.companion_service import assess_risk, companion_text
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import calc_streak, today_str

logger = get_logger("challengePlanet.reminder")


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
        checkin_result = await session.execute(
            select(CheckIn).where(
                CheckIn.challenge_id == challenge.id,
                CheckIn.date == today,
            ).limit(1)
        )
        if checkin_result.scalar_one_or_none() is None:
            unchecked.append(challenge)
    return unchecked


async def send_checkin_reminders() -> None:
    try:
        async with async_session() as session:
            unchecked = await _get_unchecked_challenges(session)
            if not unchecked:
                logger.info("No unchecked challenges found, skipping reminders.")
                return
            grouped: dict[int, list[Challenge]] = {}
            for challenge in unchecked:
                grouped.setdefault(challenge.user_id, []).append(challenge)
            logger.info("Sending reminders to %d users...", len(grouped))
            client = get_notify_client()
            checkins_repo = CheckInRepository()
            items: list[dict[str, object]] = []
            for user_id, challenges in grouped.items():
                representative = challenges[0]
                checkins = await checkins_repo.get_by_challenge(session, representative.id)
                valid = await load_valid_dates(session, representative.id)
                streak = calc_streak(valid, today_str())
                risk = assess_risk(checkins, streak, today_str())
                content = _reminder_content(risk, len(challenges))
                if len(challenges) > 1:
                    title = f"{len(challenges)} 个挑战待打卡"
                else:
                    title = f"「{representative.title}」打卡提醒"
                priority = 4 if risk["level"] == "high" else 3
                items.append(
                    {
                        "user_id": str(user_id),
                        "title": title,
                        "content": content,
                        "type": "task",
                        "priority": priority,
                        "app_id": "challengePlanet",
                        "channels": ["in_app"],
                        "link": "/challengePlanet/",
                        "data": {"challenge_count": len(challenges)},
                    }
                )
            await client.send_many(items)
            logger.info(
                "Check-in reminders processed for %d users.", len(grouped)
            )
    except Exception as e:
        logger.error("Check-in reminder task failed: %s", e)
