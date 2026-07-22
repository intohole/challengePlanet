from __future__ import annotations

import httpx
from nexus.logging import get_logger

from app.config import settings

logger = get_logger("challengePlanet.memory")

APP_NAME = "ChallengePlanet"
_RECALL_TOP_K = 3
_TIMEOUT = 8.0


async def add_memory(user_id: str, content: str) -> bool:
    if not settings.BEEMEMORY_BASE_URL:
        return False
    url = f"{settings.BEEMEMORY_BASE_URL.rstrip('/')}/api/memory/agent/add"
    payload = {"user_id": user_id, "app_name": APP_NAME, "content": content}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"X-Service-Token": settings.SERVICE_TOKEN},
            )
        if resp.status_code >= 400:
            logger.warning("beeMemory add failed: status=%d", resp.status_code)
            return False
        return True
    except Exception as e:
        logger.warning("beeMemory add error: %s", e)
        return False


async def recall_memory(user_id: str, query: str) -> list[str]:
    if not settings.BEEMEMORY_BASE_URL:
        return []
    url = f"{settings.BEEMEMORY_BASE_URL.rstrip('/')}/api/memory/agent/recall"
    payload = {
        "query": query,
        "user_id": user_id,
        "app_name": APP_NAME,
        "top_k": _RECALL_TOP_K,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"X-Service-Token": settings.SERVICE_TOKEN},
            )
        if resp.status_code >= 400:
            logger.warning("beeMemory recall failed: status=%d", resp.status_code)
            return []
        data = resp.json()
        items = data.get("data") or data.get("memories") or data.get("results") or []
        memories: list[str] = []
        for item in items:
            if isinstance(item, str):
                memories.append(item)
            elif isinstance(item, dict):
                text = item.get("content") or item.get("text") or ""
                if text:
                    memories.append(str(text))
        return memories
    except Exception as e:
        logger.warning("beeMemory recall error: %s", e)
        return []
