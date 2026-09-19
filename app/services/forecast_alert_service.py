from __future__ import annotations

import json

from nexus.logging import get_logger
from nexus.notify import get_notify_client
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import InsightRepository
from app.services.challenge_service import ChallengeService
from app.services.streak_service import today_str

logger = get_logger("challengePlanet.forecast_alert")

ALERT_TYPE = "forecast_alert"


async def _already_alerted(session: AsyncSession, challenge_id: int, date: str) -> bool:
    insight = await InsightRepository().get_by_type(session, challenge_id, ALERT_TYPE)
    if insight is None:
        return False
    try:
        payload = json.loads(insight.content)
    except (json.JSONDecodeError, TypeError):
        return False
    return str(payload.get("date", "")) == date


async def _mark_alerted(session: AsyncSession, challenge: Challenge, date: str) -> None:
    await InsightRepository().create(session, {
        "challenge_id": challenge.id,
        "user_id": challenge.user_id,
        "insight_type": ALERT_TYPE,
        "content": json.dumps({"date": date}, ensure_ascii=False),
    })
    await session.flush()


def alert_text(forecast: dict[str, object]) -> str:
    coach = str(forecast.get("coach_nudge", "") or "").strip()
    if coach:
        return coach
    return str(forecast.get("risk_window_msg", "") or "").strip()


def _compose(alerts: list[tuple[Challenge, dict[str, object], str]]) -> tuple[str, str]:
    if len(alerts) > 1:
        titles = "、".join(f"「{ch.title}」" for ch, _, _ in alerts[:2])
        return f"{len(alerts)} 个挑战节奏偏快", f"{titles} 按当前节奏今天会超目标，早点调整一下"
    challenge, _, text = alerts[0]
    return f"「{challenge.title}」节奏提醒", text


async def _collect(session: AsyncSession, today: str) -> dict[str, list]:
    challenges = await ChallengeRepository().get_all_active(session)
    service = ChallengeService()
    by_user: dict[str, list] = {}
    for challenge in challenges:
        if await _already_alerted(session, challenge.id, today):
            continue
        try:
            detail = await service.get_today_task(session, challenge.id, challenge.user_id)
        except Exception as e:
            logger.warning("forecast alert skip ch=%s: %s", challenge.id, e)
            continue
        forecast = (detail or {}).get("forecast") or {}
        if not forecast.get("enabled") or int(forecast.get("risk_level", 0) or 0) < 1:
            continue
        text = alert_text(forecast)
        if not text:
            continue
        by_user.setdefault(challenge.user_id, []).append((challenge, forecast, text))
    return by_user


async def send_forecast_alerts() -> None:
    try:
        async with async_session() as session:
            today = today_str()
            by_user = await _collect(session, today)
            if not by_user:
                logger.info("no forecast alerts to send")
                return
            client = get_notify_client()
            items: list[dict[str, object]] = []
            for user_id, alerts in by_user.items():
                title, content = _compose(alerts)
                high = any(int(f.get("risk_level", 0) or 0) >= 2 for _, f, _ in alerts)
                items.append({
                    "user_id": str(user_id),
                    "title": title,
                    "content": content,
                    "type": "task",
                    "priority": 4 if high else 3,
                    "app_id": "challengePlanet",
                    "channels": ["in_app", "email"],
                    "link": "/challengePlanet/",
                    "data": {"challenge_count": len(alerts)},
                })
                for challenge, _, _ in alerts:
                    await _mark_alerted(session, challenge, today)
            await client.send_many(items)
            await session.commit()
            logger.info("forecast alerts sent to %d users", len(items))
    except Exception as e:
        logger.error("forecast alert task failed: %s", e)
