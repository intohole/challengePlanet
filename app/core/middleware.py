from __future__ import annotations

from fastapi import FastAPI

from nexus import (
    RequestIdMiddleware,
    RateLimitMiddleware,
    register_service_auth,
    setup_cors,
    setup_exception_handlers,
)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    register_service_auth(
        app,
        public_api_prefixes=["/api/v1/auth", "/api/v1/share", "/api/auth"],
    )
    app.add_middleware(RateLimitMiddleware)
    setup_cors(app)
    setup_exception_handlers(app)
