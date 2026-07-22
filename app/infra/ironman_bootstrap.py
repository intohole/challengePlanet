from __future__ import annotations

from nexus.ironman import (
    get_bootstrap,
    init_ironman as _nexus_init_ironman,
    is_ironman_available,
)

APP_NAME = "ChallengePlanet"


async def init_ironman() -> object:
    return await _nexus_init_ironman(app_name=APP_NAME)
