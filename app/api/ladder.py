from __future__ import annotations

import json
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from nexus.logging import get_logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import now_china
from app.db.database import get_db
from app.schemas.challenge import LadderAdjustRequest
from app.repositories.challenge_repository import ChallengeRepository
from app.services.goal_rule_service import (
    is_cap_mode,
    is_ladder,
    ladder_cap_with,
    ladder_goal_day_with,
    parse_ladder_adjustments,
    total_shift_days,
)
from app.services.streak_service import day_number_of, today_str

logger = get_logger("challengePlanet.ladder")

router = APIRouter()

_MAX_ADJUSTMENT_ENTRIES = 12
_SHIFT_LIMITS = (1, 14)


def _shift_summary(challenge: object, adjustments: list[dict[str, int]]) -> dict[str, object]:
    start = str(getattr(challenge, "start_date", "") or "")
    goal_day = ladder_goal_day_with(challenge, adjustments)
    graduation_date = ""
    if goal_day is not None and start:
        graduation_date = (
            date.fromisoformat(start) + timedelta(days=goal_day - 1)
        ).isoformat()
    return {
        "adjustments": adjustments,
        "total_shift_days": total_shift_days(adjustments),
        "goal_day": goal_day,
        "graduation_date": graduation_date,
    }


@router.post("/{challenge_id}/ladder-adjust")
async def adjust_ladder(
    challenge_id: int,
    body: LadderAdjustRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict:
    challenge = await ChallengeRepository().get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise HTTPException(status_code=404, detail="挑战不存在")
    if not (is_ladder(challenge) and is_cap_mode(challenge)) or challenge.status != "active":
        raise HTTPException(status_code=422, detail="只有进行中的减量阶梯可以换挡")
    shift = int(body.shift_days or 0)
    if not _SHIFT_LIMITS[0] <= shift <= _SHIFT_LIMITS[1]:
        raise HTTPException(status_code=422, detail="后移天数需在 1-14 之间")
    today = today_str()
    start = str(challenge.start_date or "")
    if not start or today < start:
        raise HTTPException(status_code=422, detail="挑战尚未开始")
    day_number = day_number_of(start, today)
    adjustments = parse_ladder_adjustments(challenge.ladder_adjust)
    if len(adjustments) >= _MAX_ADJUSTMENT_ENTRIES:
        raise HTTPException(status_code=422, detail="换挡次数已达上限")
    candidate = adjustments + [{"day": day_number, "shift": shift}]
    today_cap = float(ladder_cap_with(challenge, day_number, candidate))
    summary = _shift_summary(challenge, candidate)
    payload = {
        "shift_days": shift,
        "effective_day": day_number,
        "today_cap": today_cap,
        **summary,
    }
    if body.preview:
        return {"preview": True, **payload}
    challenge.ladder_adjust = json.dumps(
        [{"day": a["day"], "shift": a["shift"]} for a in candidate],
        ensure_ascii=False,
    )
    payload["applied_at"] = now_china().isoformat(timespec="seconds")
    await session.commit()
    logger.info(
        "ladder adjusted: ch=%s day=%s shift=%s today_cap=%s",
        challenge_id, day_number, shift, today_cap,
    )
    return {"preview": False, **payload}
