from __future__ import annotations

import json
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.services.forecast_math import (
    WINDOW_WORDING,
    compose_window_msg,
    context_pattern,
    dominant_context,
)
from app.services.nudge_service import NudgeService
from app.services.streak_service import today_str
from app.services.target_service import recent_daily_avg

_WINDOW_DAYS = 14
_CALIBRATION_DAMPEN = 0.5


class ForecastService:
    def __init__(self) -> None:
        self._repo = CheckInRepository()
        self._insight_repo = InsightRepository()
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
        store: bool = True,
    ) -> dict[str, object]:
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
        forecast = self._nudge.evaluate(
            challenge, today_total, today_target, hour,
            hour_dist=hour_dist, is_soft_exceeded=is_soft_exceeded,
            weekday_dist=weekday_dist, day_number=day_number,
            recent_avg=recent_avg,
        )
        bias = await self._calibration_bias(session, challenge.id)
        forecast = self._nudge.apply_bias(forecast, bias)
        await self._attach_context(session, challenge, forecast, start, end)
        if store:
            await self._upsert_forecast(session, challenge, forecast)
        return forecast

    async def _attach_context(
        self, session: AsyncSession, challenge: object,
        forecast: dict[str, object], start: str, end: str,
    ) -> None:
        hours = forecast.get("risk_window_hours") or []
        if len(hours) == 2:
            rows = await self._repo.get_context_totals(
                session, challenge.id, start, end,
                hour_range=(int(hours[0]), int(hours[1])),
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

    async def _calibration_bias(self, session: AsyncSession, challenge_id: int) -> float | None:
        yesterday = (now_china() - timedelta(days=1)).strftime("%Y-%m-%d")
        last = await self._insight_repo.get_forecast(session, challenge_id)
        if last is None:
            return None
        try:
            payload = json.loads(last.content)
        except (json.JSONDecodeError, TypeError):
            return None
        if str(payload.get("date", "")) != yesterday:
            return None
        projected = float(payload.get("projected", 0) or 0)
        if projected <= 0 or not payload.get("enabled"):
            return None
        actual = await self._repo.sum_value_by_date(session, challenge_id, yesterday)
        return round((actual - projected) * _CALIBRATION_DAMPEN, 1)

    async def _upsert_forecast(
        self, session: AsyncSession, challenge: object, forecast: dict[str, object],
    ) -> None:
        today = today_str()
        last = await self._insight_repo.get_forecast(session, challenge.id)
        if last is not None:
            try:
                existed = json.loads(last.content)
            except (json.JSONDecodeError, TypeError):
                existed = {}
            if str(existed.get("date", "")) == today:
                return
        await self._insight_repo.create(session, {
            "challenge_id": challenge.id,
            "user_id": getattr(challenge, "user_id", ""),
            "insight_type": "forecast",
            "content": json.dumps({
                "date": today,
                "hour": now_china().hour,
                "enabled": bool(forecast.get("enabled")),
                "projected": forecast.get("projected", 0),
                "basis": forecast.get("basis", ""),
                "confidence": forecast.get("confidence", 0),
            }, ensure_ascii=False),
        })
        await session.flush()
