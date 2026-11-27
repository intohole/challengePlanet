"""聊天传输抽象 — 统一 SSE 流式与 JSON 非流式响应格式。
vendor: 冻结自 nexus-backend@8a9cb85^ nexus/chat（2026-11-26 退役轮）；禁就地演化，仅安全修；challengePlanet chatkit 现代化挂账业务线轮。"""

from __future__ import annotations

from typing import Any, AsyncIterator, Protocol

from fastapi import Request

from nexus.streaming import sse_chat_stream_v2


class ChatTransport(Protocol):
    async def stream(
        self, events: AsyncIterator[str | dict], request: Request | None = None
    ) -> Any: ...
    async def respond(self, result: dict[str, Any]) -> Any: ...


class SSETransport:
    async def stream(
        self, events: AsyncIterator[str | dict], request: Request | None = None
    ) -> Any:
        return sse_chat_stream_v2(events, request=request)

    async def respond(self, result: dict[str, Any]) -> Any:
        from nexus.response import success_response

        return success_response(result)
