from __future__ import annotations

from fastapi import FastAPI
from nexus import register_probe_endpoints
from nexus.scheduler import get_scheduler

from app.db.database import db_manager


def register_probe(app: FastAPI) -> None:
    register_probe_endpoints(
        app,
        app_name="challengePlanet",
        db_session_factory=lambda: db_manager.session_factory(),
        llm=True,
        notify=True,
        scheduler=get_scheduler(),
    )
