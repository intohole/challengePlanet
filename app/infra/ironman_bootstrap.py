from __future__ import annotations

import os

from nexus.ironman import (
    get_bootstrap,
    init_ironman as _nexus_init_ironman,
    is_ironman_available,
)

APP_NAME = "ChallengePlanet"

_GATEWAY_URL = os.environ.get("LLM_BASE_URL", "http://localhost:8400/api/gateway/v1")
_GATEWAY_KEY = os.environ.get("LLM_API_KEY", "gw-25f4ed50e0c057f2af6d58e8c501e99b5b30b0492b8d0b17")
_LLM_MODEL = os.environ.get("LLM_MODEL", "glm-4-flash")


async def _config_loader(app_name: str) -> dict[str, object]:
    return {
        "api_key": _GATEWAY_KEY,
        "base_url": _GATEWAY_URL,
        "model": _LLM_MODEL,
        "provider": "openai",
        "embedding_api_key": _GATEWAY_KEY,
        "embedding_base_url": _GATEWAY_URL,
        "embedding_model": "embedding-3",
        "embedding_provider": "openai",
        "embedding_dimensions": 1024,
    }


async def init_ironman() -> object:
    return await _nexus_init_ironman(app_name=APP_NAME, config_loader=_config_loader)
