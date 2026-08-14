from __future__ import annotations

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nexus.logging import get_logger

from app.config import settings
from app.db.database import async_session
from app.models.challenge import Challenge
from app.models.checkin import CheckIn
from app.services.streak_service import today_str

logger = get_logger("challengePlanet.reminder")

_NOTIFY_BASE_URL = "http://10.100.0.2:8910"


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
            async with httpx.AsyncClient(timeout=10.0) as client:
                for challenge in unchecked:
                    try:
                        resp = await client.post(
                            f"{_NOTIFY_BASE_URL}/api/notify/send",
                            headers={"X-Service-Token": settings.SERVICE_TOKEN},
                            json={
                                "user_id": challenge.user_id,
                                "app_id": "challengePlanet",
                                "type": "task",
                                "priority": 3,
                                "title": f"「{challenge.title}」打卡提醒",
                                "content": (
                                    f"今天还没打卡哦！"
                                    f"坚持{challenge.duration_days}天挑战，别断了连击！"
                                ),
                                "channels": ["in_app"],
                            },
                        )
                        if resp.status_code != 200:
                            logger.warning(
                                "Reminder send failed for user=%s status=%d",
                                challenge.user_id,
                                resp.status_code,
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
