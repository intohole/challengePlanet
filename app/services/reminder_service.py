from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.notify import get_notify_client
from nexus.logging import get_logger

from app.db.database import async_session
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.streak_service import today_str

logger = get_logger("challengePlanet.reminder")


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
            logger.info(
                "Found %d unchecked challenges, sending reminders...", len(unchecked)
            )
            client = get_notify_client()
            for challenge in unchecked:
                try:
                    await client.send(
                        user_id=str(challenge.user_id),
                        title=f"「{challenge.title}」打卡提醒",
                        content=(
                            f"今天还没打卡哦！"
                            f"坚持{challenge.duration_days}天挑战，别断了连击！"
                        ),
                        type="task",
                        priority=3,
                        app_id="challengePlanet",
                        channels=["in_app"],
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to send reminder to user %s: %s",
                        challenge.user_id,
                        e,
                    )
            logger.info(
                "Check-in reminders processed for %d challenges.", len(unchecked)
            )
    except Exception as e:
        logger.error("Check-in reminder task failed: %s", e)
