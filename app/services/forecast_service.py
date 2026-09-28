from __future__ import annotations

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.repositories.checkin_repository import CheckInRepository
from app.services.forecast_math import (
    WINDOW_WORDING,
    compose_window_msg,
    context_pattern,
    dominant_context,
    merge_context_totals,
)
from app.services.forecast_scope import supports_forecast
from app.services.nudge_service import NudgeService
from app.services.streak_service import today_str
from app.services.target_service import recent_daily_avg

_WINDOW_DAYS = 14


class ForecastService:
    def __init__(self) -> None:
        self._repo = CheckInRepository()
        self._nudge = NudgeService()

    async def build(
        self,
        session: AsyncSession,
        challenge: object,
        today_total: float,
        today_target: float,
        hour: int,
        is_soft_exceeded: bool = False,
        day_number: int | None = None,
    ) -> dict[str, object]:
        if not supports_forecast(challenge):
            return self._nudge.empty()
        now = now_china()
        start = (now - timedelta(days=_WINDOW_DAYS)).strftime("%Y-%m-%d")
        end = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        hour_dist = await self._repo.get_hourly_distribution(
            session, challenge.id, start, end
        )
        weekday_dist = await self._repo.get_hourly_distribution_by_weekday(
            session, challenge.id, now.weekday(), start, end
        )
        recent_avg = await self._recent_daily_avg(session, challenge.id)
        today_count = await self._repo.count_by_date(session, challenge.id, today_str())
        forecast = self._nudge.evaluate(
            challenge, today_total, today_target, hour,
            hour_dist=hour_dist, is_soft_exceeded=is_soft_exceeded,
            weekday_dist=weekday_dist, day_number=day_number,
            recent_avg=recent_avg, today_count=today_count,
        )
        await self._attach_context(session, challenge, forecast, start, end)
        return forecast

    async def _attach_context(
        self, session: AsyncSession, challenge: object,
        forecast: dict[str, object], start: str, end: str,
    ) -> None:
        hours = forecast.get("risk_window_hours") or []
        if len(hours) == 2:
            lo, hi = int(hours[0]), int(hours[1])
            if lo <= hi:
                rows = await self._repo.get_context_totals(
                    session, challenge.id, start, end, hour_range=(lo, hi),
                )
            else:
                rows = merge_context_totals(
                    await self._repo.get_context_totals(
                        session, challenge.id, start, end, hour_range=(lo, 23),
                    ),
                    await self._repo.get_context_totals(
                        session, challenge.id, start, end, hour_range=(0, hi),
                    ),
                )
            dom = dominant_context(rows)
            if dom:
                forecast["risk_window_context"] = dom
                span = str(forecast.get("risk_window", ""))
                direction = str(getattr(challenge, "direction", "") or "increase")
                base, action = WINDOW_WORDING.get(direction, WINDOW_WORDING["increase"])
                forecast["risk_window_msg"] = compose_window_msg(span, base, action, dom)
        all_rows = await self._repo.get_context_totals(session, challenge.id, start, end)
        pattern = context_pattern(all_rows, str(getattr(challenge, "unit", "") or ""))
        if pattern:
            forecast["context_pattern"] = pattern

    async def _recent_daily_avg(self, session: AsyncSession, challenge_id: int) -> float | None:
        return await recent_daily_avg(session, challenge_id, days=7)