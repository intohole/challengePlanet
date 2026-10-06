from __future__ import annotations

from nexus.bm_sdk import get_bm_sdk
from nexus.logging import get_logger

logger = get_logger("challengePlanet.memory")

APP_NAME = "ChallengePlanet"
_RECALL_TOP_K = 3


def _failed(data: dict) -> bool:
    return data.get("success") is False or bool(data.get("unavailable"))


async def add_memory(user_id: str, content: str) -> bool:
    data = await get_bm_sdk(app_name=APP_NAME, timeout=8.0).add_memory(
        content=content, user_id=user_id,
    )
    if _failed(data):
        logger.warning("beeMemory add failed: %s", data.get("message") or data.get("detail") or "unknown")
        return False
    return True


async def recall_memory(user_id: str, query: str) -> list[str]:
    data = await get_bm_sdk(app_name=APP_NAME, timeout=8.0).recall_memories(
        content=query, user_id=user_id, top_k=_RECALL_TOP_K, smart=False,
    )
    if _failed(data):
        logger.warning("beeMemory recall failed: %s", data.get("message") or data.get("detail") or "unknown")
        return []
    memories: list[str] = []
    for item in data.get("memories") or []:
        if isinstance(item, str):
            memories.append(item)
        elif isinstance(item, dict):
            text = item.get("content") or item.get("text") or ""
            if text:
                memories.append(str(text))
    return memories
