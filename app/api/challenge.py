from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from nexus import get_current_user_id_required
from nexus import get_datacenter_client, DOMAIN_GROWTH
from nexus.streaming import sse_event_dict, sse_response
from sqlalchemy.ext.asyncio import AsyncSession

_security = HTTPBearer(auto_error=False)


async def get_bearer_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_security),
) -> str:
    if creds is None:
        return ""
    return creds.credentials

from app.db.database import get_db
from app.schemas.challenge import (
    ChallengeConfirmRequest,
    ChallengeResponse,
    FromDecisionRequest,
    NLCreateRequest,
    ShareDataResponse,
    TodayTaskResponse,
)
from app.schemas.guidance import GuidanceResponse, ImportResponse, SharedConfigResponse
from app.services.ai_service import AIService
from app.services.challenge_service import ChallengeService
from app.services.companion_service import companion_meta, load_challenge_state
from app.services.guidance_service import GuidanceService

router = APIRouter()


def ladder_out(request: NLCreateRequest, parsed: dict[str, object]) -> dict[str, object]:
    rule = str(request.goal_rule or parsed.get("goal_rule") or "fixed")
    start = float(parsed.get("ladder_start", 0.0) or 0.0)
    goal = float(parsed.get("ladder_goal", 0.0) or 0.0)
    if request.goal_rule == "ladder" or (
        rule == "ladder" and (request.ladder_start > 0 or start > 0)
    ):
        if goal <= 0:
            goal = request.ladder_goal or float(parsed.get("target_value", 1.0) or 1.0)
        return {
            "goal_rule": "ladder",
            "goal_mode": str(request.goal_mode or parsed.get("goal_mode") or "auto"),
            "ladder_start": request.ladder_start or start or max(goal, request.target_value),
            "ladder_goal": goal,
            "ladder_interval": request.ladder_interval or int(parsed.get("ladder_interval", 1) or 1),
            "ladder_step": request.ladder_step or float(parsed.get("ladder_step", 1.0) or 1.0),
        }
    return {
        "goal_rule": "fixed" if rule == "fixed" else rule,
        "goal_mode": str(request.goal_mode or parsed.get("goal_mode") or "auto"),
        "ladder_start": 0.0, "ladder_goal": 0.0,
        "ladder_interval": 1, "ladder_step": 1.0,
    }


@router.get("", response_model=list[ChallengeResponse])
async def list_challenges(
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[ChallengeResponse]:
    service = ChallengeService()
    challenges = await service.get_user_challenges(session, user_id)
    results: list[ChallengeResponse] = []
    for c in challenges:
        results.append(await service.build_response(session, c, user_id))
    return results


@router.post("/nl-create", response_class=StreamingResponse)
async def create_challenge_nl(
    request: NLCreateRequest,
    user_id: str = Depends(get_current_user_id_required),
) -> StreamingResponse:
    ai = AIService()

    async def stream():
        yield sse_event_dict("parsing")
        try:
            parsed = await ai.parse_challenge_input(request.raw_input)
        except Exception:
            parsed = {}
        title = str(parsed.get("title", request.raw_input[:10]))
        category = str(parsed.get("category", "other"))
        duration = int(parsed.get("duration_days", 30))
        description = ""
        parsed_out = {
            "title": title,
            "category": category,
            "duration_days": duration,
            "description": description,
            "task_type": str(parsed.get("task_type", "binary")),
            "target_value": float(parsed.get("target_value", 1.0)),
            "unit": str(parsed.get("unit", "次")),
            "direction": str(parsed.get("direction", "increase")),
            "goal_type": str(parsed.get("goal_type", "hard")),
            "decompose_mode": str(parsed.get("decompose_mode", "none")),
            "slot_hours": int(parsed.get("slot_hours", 1)),
            "slot_target_value": float(parsed.get("slot_target_value", 0.0)),
            **ladder_out(request, parsed),
        }
        yield sse_event_dict("parsed", {"parsed": parsed_out})
        yield sse_event_dict("planning")
        collected: list[str] = []
        last_day = 0
        try:
            async for token in ai.generate_challenge_plan_stream(
                title, description, category, duration, request.scene_template, request.adjust_hint
            ):
                collected.append(token)
                yield sse_event_dict("token", {"token": token})
                streamed = "".join(collected)
                day_hits = [int(m) for m in re.findall(r'"day"\s*:\s*(\d+)', streamed)]
                if day_hits:
                    cur = max(day_hits)
                    if cur != last_day:
                        last_day = cur
                        yield sse_event_dict("day", {"day": cur, "total": duration})
        except Exception:
            collected = []
        plan_data = ai.parse_plan_text("".join(collected), title, duration, request.adjust_hint)
        yield sse_event_dict("preview", {
            "parsed": parsed_out,
            "plan": plan_data.get("plan", []),
            "suggestions": plan_data.get("suggestions", []),
        })

    return sse_response(stream())


@router.post("/confirm", response_model=ChallengeResponse)
async def confirm_challenge(
    request: ChallengeConfirmRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
    bearer: str = Depends(get_bearer_token),
) -> ChallengeResponse:
    service = ChallengeService()
    plan = [day.model_dump() for day in request.plan]
    challenge = await service.create_with_plan(
        session, user_id, request.title, request.description, request.category,
        request.duration_days, request.start_date, plan, request.source, request.squad_id,
        task_type=request.task_type, scene_template=request.scene_template,
        target_value=request.target_value, unit=request.unit,
        direction=request.direction, goal_type=request.goal_type,
        decompose_mode=request.decompose_mode, slot_hours=request.slot_hours,
        slot_target_value=request.slot_target_value,
        goal_rule=request.goal_rule, goal_mode=request.goal_mode,
        ladder_start=request.ladder_start, ladder_goal=request.ladder_goal,
        ladder_interval=request.ladder_interval, ladder_step=request.ladder_step,
        gender=request.gender, age=request.age, height_cm=request.height_cm,
        weight_kg=request.weight_kg, goal_weight=request.goal_weight,
        activity_level=request.activity_level,
    )
    if bearer:
        try:
            dc = await get_datacenter_client()
            await dc.report(bearer, domain=DOMAIN_GROWTH, asset_type="challenge",
                            app="challengeplanet", ref_id=challenge.id, title=request.title,
                            summary=f"{request.category} · {request.duration_days}天")
        except Exception:
            pass
    return await service.build_response(session, challenge, user_id)


@router.post("/from-decision", response_model=ChallengeResponse)
async def create_from_decision(
    request: FromDecisionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
    bearer: str = Depends(get_bearer_token),
) -> ChallengeResponse:
    service = ChallengeService()
    challenge = await service.create_from_decision(
        session, user_id, request.title, request.description, request.duration_days
    )
    if bearer:
        try:
            dc = await get_datacenter_client()
            await dc.report(bearer, domain=DOMAIN_GROWTH, asset_type="challenge",
                            app="challengeplanet", ref_id=challenge.id, title=request.title,
                            summary=f"{request.duration_days}天挑战")
        except Exception:
            pass
    return await service.build_response(session, challenge, user_id)


@router.delete("/{challenge_id}")
async def delete_challenge(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str | bool]:
    service = ChallengeService()
    result = await service.delete_challenge(session, challenge_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return result


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
    from app.services.share_service import ShareService
    data = await ShareService().get_share_data(session, challenge_id)
    return ShareDataResponse(**data)


@router.get("/{challenge_id}/guidance", response_model=GuidanceResponse)
async def get_guidance(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> GuidanceResponse:
    service = GuidanceService()
    result = await service.get_guidance(session, challenge_id, user_id)
    if result is None:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return GuidanceResponse(**result)


@router.get("/{challenge_id}/companion-status")
async def get_companion_status(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
) -> dict:
    state = await load_challenge_state(user_id, challenge_id)
    if state.get("error"):
        raise HTTPException(status_code=404, detail="挑战不存在")
    return companion_meta({**state, "challenge_id": challenge_id})


@router.get("/shared/{share_token}", response_model=SharedConfigResponse)
async def get_shared_config(
    share_token: str,
    session: AsyncSession = Depends(get_db),
) -> SharedConfigResponse:
    service = GuidanceService()
    config = await service.get_shared_config(session, share_token)
    if config is None:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")
    return SharedConfigResponse(**config)


@router.post("/import/{share_token}", response_model=ImportResponse)
async def import_shared(
    share_token: str,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ImportResponse:
    service = GuidanceService()
    challenge = await service.import_shared_config(session, share_token, user_id)
    if challenge is None:
        raise HTTPException(status_code=404, detail="分享链接无效或已过期")
    return ImportResponse(id=challenge.id, title=challenge.title, message="导入成功")


@router.post("/{challenge_id}/share", response_model=ShareDataResponse)
async def generate_share(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> ShareDataResponse:
    service = GuidanceService()
    data = await service.generate_share_token(session, challenge_id, user_id)
    if data is None:
        raise HTTPException(status_code=404, detail="挑战不存在")
    return ShareDataResponse(**data)
