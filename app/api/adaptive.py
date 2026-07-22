from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.adaptive import (
    AdaptivePendingResponse,
    AdaptiveRespondRequest,
    AdaptiveRespondResponse,
    AdaptiveSuggestionResponse,
    AdaptiveTask,
    DiagnoseApplyRequest,
    DiagnoseApplyResponse,
    DiagnoseResponse,
    DiagnosisLatestResponse,
)
from app.services.adaptive_service import AdaptiveService
from app.services.diagnosis_service import DiagnosisService

router = APIRouter()


def _bad_request(e: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(e))


def _to_suggestion_response(s: object) -> AdaptiveSuggestionResponse:
    try:
        task = json.loads(s.task_json)
    except (json.JSONDecodeError, TypeError):
        task = {}
    return AdaptiveSuggestionResponse(
        id=s.id,
        kind=s.kind,
        reason=s.reason,
        task=AdaptiveTask(**{k: task.get(k, "" if k != "day" else 0) for k in ("day", "title", "description", "tip")}),
        target_day=s.target_day,
        created_at=s.created_at,
    )


@router.get("/{challenge_id}/adaptive/pending", response_model=AdaptivePendingResponse)
async def get_pending_suggestion(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> AdaptivePendingResponse:
    service = AdaptiveService()
    try:
        suggestion = await service.get_pending(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    if suggestion is None:
        return AdaptivePendingResponse(suggestion=None)
    return AdaptivePendingResponse(suggestion=_to_suggestion_response(suggestion))


@router.post("/{challenge_id}/adaptive/{suggestion_id}/respond", response_model=AdaptiveRespondResponse)
async def respond_suggestion(
    challenge_id: int,
    suggestion_id: int,
    request: AdaptiveRespondRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> AdaptiveRespondResponse:
    service = AdaptiveService()
    try:
        result = await service.respond(session, suggestion_id, user_id, request.accept)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    task = result.get("task")
    return AdaptiveRespondResponse(
        ok=bool(result["ok"]),
        applied=bool(result["applied"]),
        task=AdaptiveTask(**task) if isinstance(task, dict) and task else None,
    )


@router.post("/{challenge_id}/diagnose", response_model=DiagnoseResponse)
async def diagnose_break(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DiagnoseResponse:
    service = DiagnosisService()
    try:
        report = await service.diagnose(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return DiagnoseResponse(**report)


@router.get("/{challenge_id}/diagnosis", response_model=DiagnosisLatestResponse)
async def get_latest_diagnosis(
    challenge_id: int,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DiagnosisLatestResponse:
    service = DiagnosisService()
    try:
        report = await service.get_latest(session, challenge_id, user_id)
    except ValueError as e:
        raise _bad_request(e)
    if report is None:
        return DiagnosisLatestResponse(report=None)
    return DiagnosisLatestResponse(report=DiagnoseResponse(**report))


@router.post("/{challenge_id}/diagnose/apply", response_model=DiagnoseApplyResponse)
async def apply_diagnosis(
    challenge_id: int,
    request: DiagnoseApplyRequest,
    user_id: str = Depends(get_current_user_id_required),
    session: AsyncSession = Depends(get_db),
) -> DiagnoseApplyResponse:
    service = DiagnosisService()
    try:
        result = await service.apply(session, challenge_id, user_id, request.action)
    except ValueError as e:
        raise _bad_request(e)
    await session.commit()
    return DiagnoseApplyResponse(**result)
