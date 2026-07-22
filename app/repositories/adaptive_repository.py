from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adaptive import AdaptiveSuggestion


class AdaptiveRepository:
    async def create(self, session: AsyncSession, data: dict[str, object]) -> AdaptiveSuggestion:
        suggestion = AdaptiveSuggestion(**data)
        session.add(suggestion)
        await session.flush()
        return suggestion

    async def get_by_id(self, session: AsyncSession, suggestion_id: int) -> AdaptiveSuggestion | None:
        result = await session.execute(
            select(AdaptiveSuggestion).where(AdaptiveSuggestion.id == suggestion_id)
        )
        return result.scalar_one_or_none()

    async def get_pending(
        self, session: AsyncSession, challenge_id: int
    ) -> AdaptiveSuggestion | None:
        result = await session.execute(
            select(AdaptiveSuggestion)
            .where(
                AdaptiveSuggestion.challenge_id == challenge_id,
                AdaptiveSuggestion.status == "pending",
            )
            .order_by(AdaptiveSuggestion.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, session: AsyncSession, suggestion: AdaptiveSuggestion, status: str
    ) -> AdaptiveSuggestion:
        suggestion.status = status
        await session.flush()
        return suggestion
