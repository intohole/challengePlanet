from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "ChallengePlanet"
    DATABASE_URL: str = f"sqlite+aiosqlite:///{Path(__file__).parent.parent / 'data' / 'challenge.db'}"
    API_PREFIX: str = "/api/v1"
    LLM_MAX_TOKENS: int = 4096
    PLANNING_TEMPERATURE: float = 0.7
    FEEDBACK_TEMPERATURE: float = 0.8
    BEEMEMORY_BASE_URL: str = "http://localhost:8700"
    SERVICE_TOKEN: str = "dev-service-token-2026"
    LION_NAMESPACE: str = "challengePlanet"
    LION_BASE_URL: str = "http://localhost:9527"
    UC_BASE_URL: str = "http://localhost:8901"
    UC_APP_KEY: str = ""
    UC_APP_SECRET: str = ""
    UC_JWT_SECRET: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
