"""FastAPI application factory for Jade's AI Humanizer daemon."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from humanizer.daemon.routes import router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(
        title="Jade's AI Humanizer Daemon",
        description="Local zero-backend REST and SSE API daemon for AI text humanization with Gemini Flash Lite.",
        version="1.2.1",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Humanization error: {str(exc)}"},
        )

    app.include_router(router)

    return app
