"""聊天上下文 — 一次会话请求的上下文数据载体。
vendor: 冻结自 nexus-backend@8a9cb85^ nexus/chat（2026-11-26 退役轮）；禁就地演化，仅安全修；challengePlanet chatkit 现代化挂账业务线轮。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.chatkit.models import ChatConversation


@dataclass
class ChatContext:
    conversation: ChatConversation
    user_message: str
    context_parts: list[str] = field(default_factory=list)
    history_messages: list[dict[str, str]] = field(default_factory=list)
    default_title: str = "新对话"
    domain_state: dict[str, Any] = field(default_factory=dict)
    usage: dict[str, int] = field(default_factory=dict)

    def set_usage(self, prompt_tokens: int, completion_tokens: int) -> None:
        self.usage = {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}

    @property
    def meta(self) -> dict[str, Any]:
        return self.conversation.meta or {}
