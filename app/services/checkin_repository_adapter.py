from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.challenge import Challenge
from app.models.sub_goal import SubGoal
from app.repositories.checkin_repository import CheckInRepository
from app.services.streak_service import today_str


async def build_sub_goal_response(
    session: AsyncSession, sg: SubGoal, challenge: Challenge
) -> dict[str, object]:
    repo = CheckInRepository()
    today = today_str()
    today_value = await repo.sum_value_by_sub_goal(session, sg.id, today)
    today_list = await repo.list_by_sub_goal(session, sg.id, today)
    target = sg.target_value if sg.target_value > 0 else challenge.slot_target_value
    pct = (today_value / target * 100) if target > 0 else 0.0
    return {
        "id": sg.id,
        "challenge_id": sg.challenge_id,
        "user_id": sg.user_id,
        "title": sg.title,
        "time_window_start": sg.time_window_start,
        "time_window_end": sg.time_window_end,
        "target_value": target,
        "goal_type": sg.goal_type,
        "weight": sg.weight,
        "order": sg.order,
        "is_active": sg.is_active,
        "created_at": sg.created_at,
        "today_value": today_value,
        "today_checkin_count": len(today_list),
        "progress_pct": round(min(pct, 100.0), 1),
    }
