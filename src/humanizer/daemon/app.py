"""FastAPI application factory for Jade's AI Humanizer daemon."""

from __future__ import annotations

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from humanizer.daemon.routes import router
from humanizer.daemon.security import SecurityHeadersMiddleware, sanitize_sensitive_string


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Jade's AI Humanizer Daemon",
        description="Local zero-backend REST and SSE API daemon for AI text humanization with Gemini Flash Lite.",
        version="1.2.2",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Configurable CORS origins, defaulting to all local origins across ports
    cors_origins_env = os.getenv("HUMANIZER_CORS_ORIGINS", "")
    if cors_origins_env.strip():
        allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
        allow_origin_regex = None
    else:
        allowed_origins = []
        allow_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allow_origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        clean_detail = sanitize_sensitive_string(str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": f"Humanization error: {clean_detail}"},
        )

    app.include_router(router)

    return app

