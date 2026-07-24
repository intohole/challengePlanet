from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from nexus import get_current_user_id_required

from app.schemas.challenge import SceneListResponse, SceneTemplateResponse
from app.services.scene_service import SceneService, SceneTemplate

router = APIRouter(prefix="/scenes", tags=["scenes"])


def _to_response(template: SceneTemplate) -> SceneTemplateResponse:
    return SceneTemplateResponse(
        scene_id=template.scene_id,
        name=template.name,
        icon=template.icon,
        color=template.color,
        description=template.description,
        task_type=template.task_type,
        default_target=template.default_target,
        unit=template.unit,
        steps=template.steps,
        difficulty_curve=template.difficulty_curve,
        sample_prompts=template.sample_prompts,
    )


@router.get("", response_model=SceneListResponse)
async def list_scenes(
    user_id: str = Depends(get_current_user_id_required),
) -> SceneListResponse:
    service = SceneService()
    scenes = [_to_response(t) for t in service.list_scenes()]
    return SceneListResponse(scenes=scenes)


@router.get("/{scene_id}", response_model=SceneTemplateResponse)
async def get_scene(
    scene_id: str,
    user_id: str = Depends(get_current_user_id_required),
) -> SceneTemplateResponse:
    service = SceneService()
    template = service.get_scene(scene_id)
    if template is None:
        raise HTTPException(status_code=404, detail=f"scene '{scene_id}' not found")
    return _to_response(template)
