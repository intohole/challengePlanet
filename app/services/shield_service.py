from __future__ import annotations

import json

from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.points_repository import ChallengeMetaRepository, StreakActionRepository

logger = get_logger("challengePlanet.shield")

SHIELD_MILESTONES = (7, 14, 30, 66)
SHIELD_CAP = 3
ACTION_SHIELD = "shield"


def _load_extra(meta: object) -> dict[str, object]:
    if meta is None:
        return {}
    try:
        data = json.loads(getattr(meta, "extra", "") or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


class ShieldService:
    def __init__(self) -> None:
        self._meta_repo = ChallengeMetaRepository()
        self._action_repo = StreakActionRepository()

    async def get_shields(self, session: AsyncSession, challenge_id: int) -> int:
        meta = await self._meta_repo.get(session, challenge_id)
        return int(_load_extra(meta).get("shields", 0))

    async def award_milestone(self, session: AsyncSession, challenge_id: int, streak: int) -> int:
        meta = await self._meta_repo.get(session, challenge_id)
        extra = _load_extra(meta)
        hit = [int(m) for m in extra.get("shield_milestones", []) if str(m).isdigit()]
        shields = int(extra.get("shields", 0))
        changed = False
        for milestone in SHIELD_MILESTONES:
            if streak >= milestone and milestone not in hit:
                hit.append(milestone)
                shields = min(SHIELD_CAP, shields + 1)
                changed = True
        if changed:
            extra["shield_milestones"] = hit
            extra["shields"] = shields
            await self._meta_repo.upsert(
                session, challenge_id, {"extra": json.dumps(extra, ensure_ascii=False)}
            )
            logger.info("shield awarded: challenge=%s streak=%s shields=%s", challenge_id, streak, shields)
        return shields

    async def consume_for_date(
        self, session: AsyncSession, challenge_id: int, user_id: str, target_date: str
    ) -> bool:
        meta = await self._meta_repo.get(session, challenge_id)
        extra = _load_extra(meta)
        shields = int(extra.get("shields", 0))
        if shields <= 0:
            return False
        extra["shields"] = shields - 1
        await self._meta_repo.upsert(
            session, challenge_id, {"extra": json.dumps(extra, ensure_ascii=False)}
        )
        await self._action_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "action": ACTION_SHIELD,
            "action_date": target_date,
            "cost": 0,
        })
        logger.info("shield consumed: challenge=%s date=%s left=%s", challenge_id, target_date, shields - 1)
        return True
