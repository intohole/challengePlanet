from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.challenge import ChallengeCreate, ChallengeResponse, TodayTaskResponse
from app.services.ai_service import AIService
from app.services.challenge_service import ChallengeService

router = APIRouter()


async def _to_response(challenge, session: AsyncSession = None) -> ChallengeResponse:
    try:
        plan = json.loads(challenge.ai_plan) if challenge.ai_plan else []
    except json.JSONDecodeError:
        plan = []
    stats = {"completed_days": 0, "total_days": challenge.duration_days, "streak": 0}
    if session is not None:
        service = ChallengeService()
        stats = await service.get_challenge_stats(session, challenge)
    return ChallengeResponse(
        id=challenge.id,
        user_id=challenge.user_id,
        title=challenge.title,
        description=challenge.description,
        category=challenge.category,
        duration_days=challenge.duration_days,
        total_days=stats["total_days"],
        completed_days=stats["completed_days"],
        streak=stats["streak"],
        start_date=challenge.start_date,
        end_date=challenge.end_date,
        status=challenge.status,
        ai_plan=plan,
        color=challenge.color,
        icon=challenge.icon,
        is_shared=challenge.is_shared,
        share_token=challenge.share_token,
        created_at=challenge.created_at,
    )


@router.get("/{user_id}", response_model=list[ChallengeResponse])
async def list_challenges(user_id: str, session: AsyncSession = Depends(get_db)) -> list[ChallengeResponse]:
    service = ChallengeService()
    challenges = await service.get_user_challenges(session, user_id)
    results: list[ChallengeResponse] = []
    for c in challenges:
        results.append(await _to_response(c, session))
    return results


@router.post("", response_class=StreamingResponse)
async def create_challenge(request: ChallengeCreate, session: AsyncSession = Depends(get_db)) -> StreamingResponse:
    ai = AIService()

    async def stream():
        async for chunk in ai.generate_challenge_plan_stream(
            request.title, request.description, request.category, request.duration_days
        ):
            yield chunk

        service = ChallengeService()
        challenge = await service.create_challenge(session, request)
        resp = await _to_response(challenge, session)
        done_data = {
            "step": "saved",
            "challenge_id": challenge.id,
            "title": challenge.title,
            "challenge": resp.model_dump(mode="json"),
        }
        yield f"data: {json.dumps(done_data, ensure_ascii=False)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/{challenge_id}/today", response_model=TodayTaskResponse)
async def get_today_task(challenge_id: int, user_id: str = "", session: AsyncSession = Depends(get_db)) -> TodayTaskResponse:
    service = ChallengeService()
    result = await service.get_today_task(session, challenge_id, user_id)
    if result is None:
        return TodayTaskResponse(challenge_id=challenge_id, day_number=1, date="", task={})
    return result
