from __future__ import annotations

from fastapi import APIRouter, Depends
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.sub_goal_repository import SubGoalRepository
from app.schemas.sub_goal import (
    SubGoalAutoDecomposeRequest,
    SubGoalAutoDecomposeResponse,
    SubGoalBatchCreate,
    SubGoalCreate,
    SubGoalResponse,
)
from app.services.ai_service import AIService
from app.services.checkin_repository_adapter import build_sub_goal_response
from app.api._common import bad_request

router = APIRouter()


@router.get("/{challenge_id}/sub-goals", response_model=list[SubGoalResponse])
async def list_sub_goals(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[SubGoalResponse]:
    challenge_repo = ChallengeRepository()
    sub_goal_repo = SubGoalRepository()
    challenge = await challenge_repo.get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request(ValueError("挑战不存在"))
    sub_goals = await sub_goal_repo.get_by_challenge(session, challenge_id)
    return [await build_sub_goal_response(session, sg, challenge) for sg in sub_goals]


@router.post("/{challenge_id}/sub-goals", response_model=list[SubGoalResponse])
async def create_sub_goals(
    challenge_id: int,
    request: SubGoalBatchCreate,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[SubGoalResponse]:
    challenge_repo = ChallengeRepository()
    sub_goal_repo = SubGoalRepository()
    challenge = await challenge_repo.get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request(ValueError("挑战不存在"))
    if len(request.sub_goals) > 4:
        raise bad_request(ValueError("最多4个时段子目标"))
    items = [
        {
            "challenge_id": challenge_id,
            "user_id": user_id,
            "title": sg.title,
            "time_window_start": sg.time_window_start,
            "time_window_end": sg.time_window_end,
            "target_value": sg.target_value,
            "goal_type": sg.goal_type,
            "weight": sg.weight,
            "order": sg.order,
        }
        for sg in request.sub_goals
    ]
    created = await sub_goal_repo.batch_create(session, items)
    await session.commit()
    return [await build_sub_goal_response(session, sg, challenge) for sg in created]


@router.post("/{challenge_id}/sub-goals/auto-decompose", response_model=SubGoalAutoDecomposeResponse)
async def auto_decompose(
    challenge_id: int,
    request: SubGoalAutoDecomposeRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> SubGoalAutoDecomposeResponse:
    challenge_repo = ChallengeRepository()
    sub_goal_repo = SubGoalRepository()
    challenge = await challenge_repo.get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request(ValueError("挑战不存在"))

    ai = AIService()
    suggestion = await ai.suggest_decompose(
        title=challenge.title,
        description=challenge.description,
        category=challenge.category,
        target_value=challenge.target_value,
        unit=challenge.unit,
        direction=challenge.direction,
        goal_type=challenge.goal_type,
        duration_days=challenge.duration_days,
    )

    if suggestion.get("decompose_mode") != "time_slot" or not suggestion.get("sub_goals"):
        await challenge_repo.update(session, challenge_id, {
            "decompose_mode": "none",
            "slot_hours": 1,
            "slot_target_value": 0.0,
        })
        await session.commit()
        return SubGoalAutoDecomposeResponse(
            sub_goals=[],
            message=str(suggestion.get("rationale", "暂不拆解，先观察打卡模式")),
        )

    await sub_goal_repo.deactivate_by_challenge(session, challenge_id)
    slot_hours = int(suggestion.get("slot_hours", request.slot_hours))
    slot_target_value = float(suggestion.get("slot_target_value", request.target_per_slot))
    await challenge_repo.update(session, challenge_id, {
        "decompose_mode": "time_slot",
        "slot_hours": slot_hours,
        "slot_target_value": slot_target_value,
    })

    items: list[dict[str, object]] = []
    for idx, sg in enumerate(suggestion["sub_goals"]):
        items.append({
            "challenge_id": challenge_id,
            "user_id": user_id,
            "title": str(sg.get("title", f"时段{idx + 1}")),
            "time_window_start": str(sg.get("time_window_start", "")),
            "time_window_end": str(sg.get("time_window_end", "")),
            "target_value": float(sg.get("target_value", 0.0)) or slot_target_value,
            "goal_type": str(sg.get("goal_type", challenge.goal_type)),
            "weight": float(sg.get("weight", 1.0)),
            "order": idx + 1,
        })
    created = await sub_goal_repo.batch_create(session, items)
    await session.commit()
    return SubGoalAutoDecomposeResponse(
        sub_goals=[await build_sub_goal_response(session, sg, challenge) for sg in created],
        message=str(suggestion.get("rationale", "已自动拆解时段目标")),
    )


@router.delete("/{challenge_id}/sub-goals/{sub_goal_id}")
async def delete_sub_goal(
    challenge_id: int,
    sub_goal_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    challenge_repo = ChallengeRepository()
    sub_goal_repo = SubGoalRepository()
    challenge = await challenge_repo.get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request(ValueError("挑战不存在"))
    sub_goal = await sub_goal_repo.get_by_id(session, sub_goal_id)
    if sub_goal is None or sub_goal.challenge_id != challenge_id:
        raise bad_request(ValueError("子目标不存在"))
    await sub_goal_repo.delete(session, sub_goal)
    await session.commit()
    return {"ok": True}
