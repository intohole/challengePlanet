"""历史中间件 — 注入最近对话历史作为上下文。
vendor: 冻结自 nexus-backend@8a9cb85^ nexus/chat（2026-11-26 退役轮）；禁就地演化，仅安全修；challengePlanet chatkit 现代化挂账业务线轮。"""

from __future__ import annotations

from app.chatkit.context import ChatContext
from app.chatkit.middleware.base import BaseChatMiddleware
from app.chatkit.store import ChatStore


class HistoryMiddleware(BaseChatMiddleware):
    def __init__(self, store: ChatStore, max_turns: int = 10) -> None:
        self._store = store
        self._max_turns = max_turns

    async def before(self, context: ChatContext) -> None:
        messages = await self._store.recent_messages(context.conversation.id, self._max_turns * 2)
        context.history_messages = [{"role": m.role, "content": m.content} for m in messages]
