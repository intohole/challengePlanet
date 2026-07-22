from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.challenge import (
    ChallengeConfirmRequest,
    ChallengeResponse,
    FromDecisionRequest,
    NLCreateRequest,
    ShareDataResponse,
    TodayTaskResponse,
)
from app.services.ai_service import AIService
from app.services.challenge_service import ChallengeService

router = APIRouter()


def _sse(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _to_response(challenge: object, item: dict[str, object]) -> ChallengeResponse:
    c = challenge
    stats = item["stats"]
    try:
        plan = json.loads(c.ai_plan) if c.ai_plan else []
    except json.JSONDecodeError:
        plan = []
    return ChallengeResponse(
        id=c.id,
        user_id=c.user_id,
        title=c.title,
        description=c.description,
        category=c.category,
        duration_days=c.duration_days,
        total_days=stats["total_days"],
        completed_days=stats["completed_days"],
        streak=stats["streak"],
        start_date=c.start_date,
        end_date=c.end_date,
        status=c.status,
        ai_plan=plan,
        color=c.color,
        icon=c.icon,
        is_shared=c.is_shared,
        share_token=c.share_token,
        source=str(item.get("source", "manual")),
        today_checked=bool(item.get("today_checked", False)),
        mercy=item.get("mercy", {}),
        created_at=c.created_at,
    )


async def _build_response(
    session: AsyncSession, challenge: object, user_id: str
) -> ChallengeResponse:
    service = ChallengeService()
    item = await service.build_list_item(session, challenge, user_id)
    return _to_response(challenge, item)


@router.get("", response_model=list[ChallengeResponse])
async def list_challenges(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[ChallengeResponse]:
    service = ChallengeService()
    challenges = await service.get_user_challenges(session, user_id)
    results: list[ChallengeResponse] = []
    for c in challenges:
        results.append(await _build_response(session, c, user_id))
    return results


@router.post("/nl-create", response_class=StreamingResponse)
async def create_challenge_nl(
    request: NLCreateRequest,
    user_id: str = Depends(get_current_user_id_required),
) -> StreamingResponse:
    ai = AIService()

    async def stream():
        yield _sse({"step": "parsing"})
        try:
            parsed = await ai.parse_challenge_input(request.raw_input)
        except Exception:
            parsed = {}
        title = str(parsed.get("title", request.raw_input[:10]))
        category = str(parsed.get("category", "other"))
        duration = int(parsed.get("duration_days", 30))
        description = str(parsed.get("description", request.raw_input))
        parsed_out = {
            "title": title,
            "category": category,
            "duration_days": duration,
            "description": description,
        }
        yield _sse({"step": "parsed", "parsed": parsed_out})
        yield _sse({"step": "planning"})
        collected: list[str] = []
        try:
            async for token in ai.generate_challenge_plan_stream(title, description, category, duration):
                collected.append(token)
                yield _sse({"step": "token", "token": token})
        except Exception:
            collected = []
        plan_data = ai.parse_plan_text("".join(collected), title, duration)
        yield _sse({
            "step": "preview",
            "parsed": parsed_out,
            "plan": plan_data.get("plan", []),
            "suggestions": plan_data.get("suggestions", []),
        })

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.post("/confirm", response_model=ChallengeResponse)
async def confirm_challenge(
    request: ChallengeConfirmRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ChallengeResponse:
    service = ChallengeService()
    plan = [day.model_dump() for day in request.plan]
    challenge = await service.create_with_plan(
        session, user_id, request.title, request.description, request.category,
        request.duration_days, request.start_date, plan, request.source, request.squad_id,
    )
    await session.commit()
    return await _build_response(session, challenge, user_id)


@router.post("/from-decision", response_model=ChallengeResponse)
async def create_from_decision(
    request: FromDecisionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ChallengeResponse:
    service = ChallengeService()
    challenge = await service.create_from_decision(
        session, user_id, request.title, request.description, request.duration_days
    )
    await session.commit()
    return await _build_response(session, challenge, user_id)


@router.get("/{challenge_id}/today", response_model=TodayTaskResponse)
async def get_today_task(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> TodayTaskResponse:
    service = ChallengeService()
    result = await service.get_today_task(session, challenge_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return TodayTaskResponse(**result)


@router.get("/{challenge_id}/share-data", response_model=ShareDataResponse)
async def get_share_data(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ShareDataResponse:
    service = ChallengeService()
    challenge = await service.get_challenge(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise HTTPException(status_code=404, detail="挑战不存在")
    data = await service.get_share_data(session, challenge_id)
    await session.commit()
    return ShareDataResponse(**data)
