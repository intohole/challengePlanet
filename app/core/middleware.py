from __future__ import annotations

from fastapi import FastAPI

from nexus import (
    RequestIdMiddleware,
    ServiceAuthMiddleware,
    RateLimitMiddleware,
    setup_cors,
    setup_exception_handlers,
)


def register_middleware(app: FastAPI) -> None:
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        ServiceAuthMiddleware,
        whitelist_paths=[
            "/health",
            "/health/detailed",
            "/api/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/",
            "/login",
            "/static",
        ],
        public_api_prefixes=["/api/v1/auth", "/api/v1/share"],
    )
    app.add_middleware(RateLimitMiddleware)
    setup_cors(app)
    setup_exception_handlers(app)
