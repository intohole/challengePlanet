from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from nexus import get_current_user_id_required
from nexus.streaming import sse_event_dict, sse_response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.repositories.challenge_repository import ChallengeRepository
from app.repositories.checkin_repository import CheckInRepository, InsightRepository
from app.schemas.checkin import (
    CheckInCreate,
    CheckInMetaPatch,
    CheckInPatchRequest,
    CheckInResponse,
    CheckInResultResponse,
    DateActionRequest,
    DateActionResponse,
    FeedbackStreamRequest,
    ForecastResponse,
    InsightStreamRequest,
    MercyStatusResponse,
    RepairResponse,
)
from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_service import AIService
from app.services.ai_text_sanitizer import sanitize_coach_text
from app.services.checkin_background import (
    build_feedback_prompt_inputs,
    feedback_fallback,
    safe_declaration,
)
from app.services.checkin_service import CheckInService
from app.services.mercy_service import MercyService
from app.services.streak_service import week_dates_of
from app.api._common import bad_request

router = APIRouter()

_feedback_locks: dict[int, asyncio.Lock] = {}


@router.post("/{challenge_id}/checkin", response_model=CheckInResultResponse)
async def do_checkin(
    challenge_id: int,
    request: CheckInCreate,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CheckInResultResponse:
    service = CheckInService()
    try:
        result = await service.do_checkin(
            session, challenge_id, user_id,
            value=request.value,
            mood=request.mood,
            reflection=request.reflection,
            context_tag=request.context_tag,
            timestamp=request.timestamp,
            sport_type=request.sport_type,
            sport_minutes=request.sport_minutes,
        )
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return CheckInResultResponse(
        checkin=CheckInResponse.model_validate(result["checkin"]),
        ai_feedback=str(result["ai_feedback"]),
        points_earned=int(result["points_earned"]),
        chest_points=int(result["chest_points"]),
        streak=int(result["streak"]),
        already_checked=bool(result["already_checked"]),
        declaration=str(result.get("declaration", "")),
        shields=int(result.get("shields", 0)),
        today_total=float(result.get("today_total", 0)),
        today_target=float(result.get("today_target", 0)),
        dynamic_baseline=float(result.get("dynamic_baseline", 0)),
        remaining=float(result.get("remaining", 0)),
        is_soft_exceeded=bool(result.get("is_soft_exceeded", False)),
        soft_exceeded_amount=float(result.get("soft_exceeded_amount", 0)),
        coach_nudge=str(result.get("coach_nudge", "")),
        nudge_level=int(result.get("nudge_level", 0)),
        forecast=ForecastResponse(**result.get("forecast", {})),
    )


@router.patch("/{challenge_id}/checkin/today", response_model=CheckInResponse)
async def patch_today_checkin(
    challenge_id: int,
    request: CheckInPatchRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CheckInResponse:
    service = CheckInService()
    try:
        checkin = await service.update_today_reflection(
            session, challenge_id, user_id, request.mood, request.reflection
        )
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return CheckInResponse.model_validate(checkin)


@router.delete("/{challenge_id}/checkins/{checkin_id}")
async def delete_checkin(
    challenge_id: int,
    checkin_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> dict[str, bool]:
    service = CheckInService()
    try:
        await service.delete_checkin(session, checkin_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return {"ok": True}


@router.patch("/{challenge_id}/checkins/{checkin_id}/meta", response_model=CheckInResponse)
async def patch_checkin_meta(
    challenge_id: int,
    checkin_id: int,
    request: CheckInMetaPatch,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> CheckInResponse:
    service = CheckInService()
    try:
        checkin = await service.update_checkin_meta(
            session, challenge_id, checkin_id, user_id,
            context_tag=request.context_tag, mood=request.mood,
        )
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return CheckInResponse.model_validate(checkin)


@router.post("/{challenge_id}/feedback/stream")
async def stream_feedback(
    challenge_id: int,
    request: FeedbackStreamRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    challenge = await ChallengeRepository().get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request("挑战不存在")
    repo = CheckInRepository()
    checkin = await repo.get_by_id(session, request.checkin_id)
    if checkin is None or checkin.challenge_id != challenge_id:
        raise bad_request("打卡记录不存在")

    async def gen():
        if checkin.ai_feedback and not request.force:
            yield sse_event_dict("done", {
                "content": sanitize_coach_text(checkin.ai_feedback),
                "declaration": str(checkin.declaration or ""),
                "cached": True,
            })
            return
        lock = _feedback_locks.setdefault(request.checkin_id, asyncio.Lock())
        try:
            async with lock:
                fresh = await repo.get_by_id(session, request.checkin_id)
                if fresh is None:
                    yield sse_event_dict("done", {"content": "", "declaration": ""})
                    return
                if fresh.ai_feedback and not request.force:
                    yield sse_event_dict("done", {
                        "content": sanitize_coach_text(fresh.ai_feedback),
                        "declaration": str(fresh.declaration or ""),
                        "cached": True,
                    })
                    return
                ai = AIService()
                inputs = await build_feedback_prompt_inputs(session, fresh, challenge)
                pieces: list[str] = []
                try:
                    async for piece in ai.stream_daily_feedback(**inputs):
                        pieces.append(piece)
                        yield sse_event_dict("token", {"token": piece})
                except Exception:
                    content = feedback_fallback(
                        fresh.day_number, fresh.mood, bool(inputs.get("is_soft_exceeded")),
                    )
                    declaration = ""
                else:
                    content = sanitize_coach_text(
                        "".join(pieces).strip(),
                        system=AIService._feedback_system(inputs["mood"]),
                        fallback="",
                    )
                    declaration = await safe_declaration(ai, challenge.title, fresh.day_number)
                if content:
                    await repo.update(session, fresh, {
                        "ai_feedback": content, "declaration": declaration,
                    })
                    await session.commit()
                yield sse_event_dict("done", {
                    "content": content, "declaration": declaration,
                })
        finally:
            _feedback_locks.pop(request.checkin_id, None)

    return sse_response(gen())


@router.post("/{challenge_id}/mend", response_model=DateActionResponse)
async def mend_checkin(
    challenge_id: int,
    request: DateActionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DateActionResponse:
    service = MercyService()
    try:
        result = await service.mend(session, challenge_id, user_id, request.date)
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return DateActionResponse(**result)


@router.post("/{challenge_id}/freeze", response_model=DateActionResponse)
async def freeze_checkin(
    challenge_id: int,
    request: DateActionRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DateActionResponse:
    service = MercyService()
    try:
        result = await service.freeze(session, challenge_id, user_id, request.date)
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return DateActionResponse(**result)


@router.post("/{challenge_id}/repair", response_model=RepairResponse)
async def repair_streak(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> RepairResponse:
    service = MercyService()
    try:
        result = await service.repair(session, challenge_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    await session.commit()
    return RepairResponse(**result)


@router.get("/{challenge_id}/mercy", response_model=MercyStatusResponse)
async def get_mercy_status(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> MercyStatusResponse:
    service = MercyService()
    try:
        result = await service.get_mercy_status(session, challenge_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    return MercyStatusResponse(**result)


@router.get("/{challenge_id}/checkins", response_model=list[CheckInResponse])
async def get_checkins(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> list[CheckInResponse]:
    service = CheckInService()
    try:
        checkins = await service.get_checkins(session, challenge_id, user_id)
    except ValueError as e:
        raise bad_request(e)
    return [_sanitized_checkin(c) for c in checkins]


def _sanitized_checkin(c) -> CheckInResponse:
    data = CheckInResponse.model_validate(c).model_dump()
    data["ai_feedback"] = sanitize_coach_text(c.ai_feedback)
    return CheckInResponse(**data)


@router.post("/{challenge_id}/insight/stream")
async def stream_insight(
    challenge_id: int,
    request: InsightStreamRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    challenge = await ChallengeRepository().get_by_id(session, challenge_id)
    if challenge is None or challenge.user_id != user_id:
        raise bad_request("挑战不存在")
    insight_repo = InsightRepository()
    latest = await insight_repo.get_latest_weekly(session, challenge_id)
    week_dates = set(week_dates_of())
    fresh = bool(
        latest and latest.created_at
        and latest.created_at.date().strftime("%Y-%m-%d") in week_dates
    )

    async def gen():
        if fresh and not request.force:
            yield sse_event_dict("done", {"content": latest.content, "cached": True})
            return
        checkins = await CheckInRepository().get_by_challenge(session, challenge_id)
        checkin_data = [
            {
                "day_number": c.day_number,
                "mood": c.mood,
                "reflection": c.reflection,
                "value": c.value,
                "timestamp": c.timestamp.isoformat(),
                "date": c.date,
            }
            for c in checkins
        ]
        pieces: list[str] = []
        ai = AIAnalysisService()
        async for piece in ai.stream_weekly_report(
            challenge.title, checkin_data, challenge.duration_days
        ):
            pieces.append(piece)
            yield sse_event_dict("token", {"token": piece})
        content = sanitize_coach_text("".join(pieces).strip(), max_len=512)
        if not content:
            content = "本周还没有足够记录，先打几天卡再来看看洞察吧"
        await insight_repo.create(session, {
            "challenge_id": challenge_id,
            "user_id": challenge.user_id,
            "insight_type": "weekly",
            "content": content,
        })
        await session.commit()
        yield sse_event_dict("done", {"content": content})

    return sse_response(gen())
