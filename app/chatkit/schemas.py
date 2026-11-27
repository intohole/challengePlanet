"""聊天 API 契约 — 统一会话与消息的请求/响应模型。
vendor: 冻结自 nexus-backend@8a9cb85^ nexus/chat（2026-11-26 退役轮）；禁就地演化，仅安全修；challengePlanet chatkit 现代化挂账业务线轮。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str | None = None


class ConversationUpdate(BaseModel):
    title: str | None = None
    status: str | None = None
    meta: dict[str, Any] | None = None


class MessageCreate(BaseModel):
    content: str = Field(min_length=1)
