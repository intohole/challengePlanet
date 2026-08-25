from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.api._common import bad_request
from app.db.database import get_db
from app.repositories.challenge_repository import ChallengeRepository
from app.schemas.diet import (
    DietEstimateRequest,
    DietEstimateResponse,
    DietTargetResponse,
    WeightRecordRequest,
    WeightTrendResponse,
)
from app.services.challenge_service import ChallengeService
from app.services.diet_service import DietService, calc_daily_target

router = APIRouter()


def _get_challenge_or_404(challenge, challenge_id: int) -> object:
    if challenge is None:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return challenge


def _check_owner(challenge, user_id: str) -> None:
    if challenge.user_id != user_id:
        raise HTTPException(status_code=404, detail="挑战不存在")


@router.post("/{challenge_id}/diet/estimate", response_model=DietEstimateResponse)
async def estimate_calories(
    challenge_id: int,
    request: DietEstimateRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DietEstimateResponse:
    repo = ChallengeRepository()
    challenge = await repo.get_by_id(session, challenge_id)
    _get_challenge_or_404(challenge, challenge_id)
    _check_owner(challenge, user_id)
    if str(getattr(challenge, "task_type", "")) != "diet":
        raise bad_request("该挑战非饮食控制类型")
    result = await DietService().estimate_calories(request.description, challenge)
    return DietEstimateResponse(**result)


@router.get("/{challenge_id}/diet/target", response_model=DietTargetResponse)
async def get_diet_target(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DietTargetResponse:
    repo = ChallengeRepository()
    challenge = await repo.get_by_id(session, challenge_id)
    _get_challenge_or_404(challenge, challenge_id)
    _check_owner(challenge, user_id)
    weight = float(getattr(challenge, "weight_kg", 0) or 0)
    goal = float(getattr(challenge, "goal_weight", 0) or 0)
    cal = calc_daily_target(
        str(getattr(challenge, "gender", "") or ""),
        int(getattr(challenge, "age", 0) or 0),
        float(getattr(challenge, "height_cm", 0) or 0),
        weight, goal,
        int(getattr(challenge, "activity_level", 2) or 2),
        int(getattr(challenge, "duration_days", 30) or 30),
    )
    return DietTargetResponse(
        target_kcal=float(cal["target_kcal"]),
        deficit_kcal=float(cal["deficit_kcal"]),
        tdee_kcal=float(cal["tdee_kcal"]),
        bmr_kcal=float(cal["bmr_kcal"]),
        current_weight=weight,
        goal_weight=goal,
    )


@router.post("/{challenge_id}/weight", response_model=dict[str, object])
async def record_weight(
    challenge_id: int,
    request: WeightRecordRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    service = ChallengeService()
    challenge = await service.get_challenge(session, challenge_id)
    _get_challenge_or_404(challenge, challenge_id)
    _check_owner(challenge, user_id)
    if request.weight_kg <= 20 or request.weight_kg > 400:
        raise bad_request("体重需在20-400kg之间")
    result = await DietService().record_weight(
        session, challenge_id, user_id, request.weight_kg, request.date
    )
    await session.commit()
    return result


@router.get("/{challenge_id}/weight/trend", response_model=WeightTrendResponse)
async def get_weight_trend(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> WeightTrendResponse:
    service = ChallengeService()
    challenge = await service.get_challenge(session, challenge_id)
    _get_challenge_or_404(challenge, challenge_id)
    _check_owner(challenge, user_id)
    result = await DietService().get_weight_trend(session, challenge_id, user_id)
    return WeightTrendResponse(**result)