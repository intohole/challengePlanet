"""聊天中间件协议 — 洋葱模型管道扩展点。
vendor: 冻结自 nexus-backend@8a9cb85^ nexus/chat（2026-11-26 退役轮）；禁就地演化，仅安全修；challengePlanet chatkit 现代化挂账业务线轮。"""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from app.chatkit.context import ChatContext


class ChatMiddleware(Protocol):
    async def before(self, context: ChatContext) -> None: ...
    async def after(self, context: ChatContext, reply: str) -> None: ...
    async def wrap_stream(
        self, context: ChatContext, stream: AsyncIterator[str | dict]
    ) -> AsyncIterator[str | dict]: ...


class BaseChatMiddleware:
    async def before(self, context: ChatContext) -> None:
        return None

    async def after(self, context: ChatContext, reply: str) -> None:
        return None

    async def wrap_stream(
        self, context: ChatContext, stream: AsyncIterator[str | dict]
    ) -> AsyncIterator[str | dict]:
        async for chunk in stream:
            yield chunk
