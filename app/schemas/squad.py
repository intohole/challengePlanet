from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SquadCreateRequest(BaseModel):
    name: str = Field(..., description="小队名称", max_length=64)
    nickname: str = Field("", description="我的队内昵称", max_length=64)


class SquadJoinRequest(BaseModel):
    invite_code: str = Field(..., description="邀请码")
    nickname: str = Field("", description="我的队内昵称", max_length=64)


class NudgeRequest(BaseModel):
    to_user_id: str = Field(..., description="被戳的用户ID")


class SquadResponse(BaseModel):
    id: int
    name: str
    invite_code: str
    created_by: str
    member_count: int = 0
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SquadBoardMember(BaseModel):
    user_id: str
    nickname: str = ""
    checked_today: bool = False
    week_points: int = 0


class SquadBoardResponse(BaseModel):
    squad_id: int
    name: str
    invite_code: str
    week_key: str
    members: list[SquadBoardMember] = Field(default_factory=list)
