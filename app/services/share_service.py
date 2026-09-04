from __future__ import annotations

import json
from datetime import datetime

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository
from app.repositories.points_repository import ChallengeMetaRepository
from app.services.ai_service import AIService
from app.services.mercy_service import load_valid_dates
from app.services.streak_service import calc_streak, today_str

logger = get_logger("challengePlanet.share")


def _calc_progress(completed_days: int, duration_days: int) -> float:
    if duration_days <= 0:
        return 0.0
    return round(completed_days * 100.0 / duration_days, 1)


class ShareService:
    def __init__(self) -> None:
        self._repo = ChallengeRepository()
        self._checkin_repo = CheckInRepository()
        self._meta_repo = ChallengeMetaRepository()
        self._ai = AIService()

    async def get_share_data(
        self, session: AsyncSession, challenge_id: int,
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_id(session, challenge_id)
        if challenge is None:
            return None
        data = await self._build_share_data(session, challenge)
        await session.commit()
        return data

    async def get_share_data_by_token(
        self, session: AsyncSession, share_token: str,
    ) -> dict[str, object] | None:
        challenge = await self._repo.get_by_share_token(session, share_token)
        if challenge is None:
            return None
        return await self._build_share_data(session, challenge)

    async def _build_share_data(
        self, session: AsyncSession, challenge: Challenge,
    ) -> dict[str, object]:
        checkins = await self._checkin_repo.get_by_challenge(session, challenge.id)
        valid = await load_valid_dates(session, challenge.id)
        streak = calc_streak(valid, today_str())
        completed_days = len(checkins)
        start_date = datetime.strptime(challenge.start_date, "%Y-%m-%d")
        current_day = min((now_china() - start_date).days + 1, challenge.duration_days)
        progress = _calc_progress(completed_days, challenge.duration_days)
        share_quote = await self._get_or_create_quote(session, challenge, streak)
        share_text = (
            f"🎯 {challenge.title}\n"
            f"已坚持 {completed_days}/{challenge.duration_days} 天 ({progress:.0f}%)\n"
            f"🔥 连续 {streak} 天\n"
            f"在星轨挑战，用AI规划每一天的坚持"
        )
        return {
            "challenge_id": challenge.id, "title": challenge.title,
            "duration_days": challenge.duration_days, "current_day": current_day,
            "total_checkins": completed_days, "streak": streak,
            "progress_pct": round(progress, 1), "share_text": share_text,
            "share_token": challenge.share_token, "share_quote": share_quote,
        }

    async def _get_or_create_quote(
        self, session: AsyncSession, challenge: Challenge, streak: int,
    ) -> str:
        meta = await self._meta_repo.get(session, challenge.id)
        cached: dict[str, object] = {}
        if meta is not None and meta.extra:
            try:
                cached = json.loads(meta.extra)
            except json.JSONDecodeError:
                cached = {}
        quote = str(cached.get("share_quote", ""))
        if quote:
            return quote
        try:
            quote = await self._ai.generate_share_quote(challenge.title, streak)
        except Exception as e:
            logger.warning("share quote fallback: %s", e)
            quote = "坚持，是最好的答案"
        cached["share_quote"] = quote
        await self._meta_repo.upsert(session, challenge.id, {"extra": json.dumps(cached, ensure_ascii=False)})
        return quote
