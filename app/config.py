from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "星轨挑战"
    APP_VERSION: str = "1.0.0"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).parent.parent / 'data' / 'challenge.db'}"
    API_PREFIX: str = "/api/v1"
    LLM_MAX_TOKENS: int = 4096
    PLANNING_TEMPERATURE: float = 0.7
    FEEDBACK_TEMPERATURE: float = 0.8
    BEEMEMORY_BASE_URL: str = os.environ.get("BEEMEMORY_BASE_URL", "http://edge-01:8700")
    NOTIFY_CENTER_URL: str = os.environ.get("NOTIFY_CENTER_URL", "http://edge-01:8910")
    SERVICE_TOKEN: str = os.environ.get("SERVICE_TOKEN", "")
    LION_NAMESPACE: str = "challengePlanet"
    LION_BASE_URL: str = os.environ.get("LION_BASE_URL", "http://edge-01:9527")
    UC_BASE_URL: str = "https://songguokr.com/uc-api"
    UC_APP_KEY: str = os.environ.get("UC_APP_KEY", "")
    UC_APP_SECRET: str = os.environ.get("UC_APP_SECRET", "")
    UC_JWT_SECRET: str = os.environ.get("UC_JWT_SECRET", "")

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
