"""REST and SSE route definitions for Jade's AI Humanizer daemon."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from humanizer.client import Humanizer
from humanizer.models import ModePreset, ReadingLevelPreset, TonePreset

router = APIRouter()


class HumanizeRequest(BaseModel):
    text: Optional[str] = Field(None, description="Text to humanize")
    mode: str = Field("budget", description="Humanization mode: 'budget' or 'deep'")
    tone: str = Field("neutral", description="Tone preset: 'neutral', 'casual', 'academic', 'professional'")
    reading_level: str = Field("general", description="Reading level: 'general', 'middle_school', 'high_school', 'college'")
    preserve_markdown: bool = Field(True, description="Preserve markdown structures intact")


class HumanizeResponse(BaseModel):
    humanized_text: str
    original_text: str
    mode: str
    tone: str
    reading_level: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    buzzwords_replaced: list[str]
    flesch_reading_ease: float


def get_client() -> Humanizer:
    mock_mode = os.getenv("HUMANIZER_MOCK_MODE", "").lower() in ("1", "true", "yes")
    return Humanizer(mock_mode=mock_mode)


@router.get("/health", summary="Daemon Health Check")
def health_check() -> dict[str, Any]:
    """Check health and configuration status of the local humanizer daemon."""
    api_key_configured = bool(os.getenv("GEMINI_API_KEY"))
    return {
        "status": "healthy",
        "version": "1.0.0",
        "engine": "gemini-2.5-flash-lite",
        "api_key_configured": api_key_configured,
        "default_mode": "budget",
    }


@router.post("/v1/humanize", response_model=HumanizeResponse, summary="Humanize Text")
def humanize_text(payload: HumanizeRequest) -> HumanizeResponse:
    """Humanize input text synchronously."""
    if payload.text is None:
        raise HTTPException(status_code=422, detail="Field 'text' is required")
    if payload.mode not in ("budget", "deep"):
        raise HTTPException(status_code=422, detail=f"Invalid mode '{payload.mode}'. Must be 'budget' or 'deep'")

    if not payload.text:
        return HumanizeResponse(
            humanized_text="",
            original_text="",
            mode=payload.mode,
            tone=payload.tone,
            reading_level=payload.reading_level,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            buzzwords_replaced=[],
            flesch_reading_ease=100.0,
        )

    client = get_client()
    result = client.humanize(
        text=payload.text,
        mode=payload.mode,  # type: ignore[arg-type]
        tone=payload.tone,  # type: ignore[arg-type]
        reading_level=payload.reading_level,  # type: ignore[arg-type]
        preserve_markdown=payload.preserve_markdown,
    )

    return HumanizeResponse(
        humanized_text=result.text,
        original_text=result.original_text,
        mode=result.mode,
        tone=result.tone,
        reading_level=result.reading_level,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        buzzwords_replaced=result.buzzwords_replaced,
        flesch_reading_ease=result.flesch_reading_ease,
    )


@router.post("/v1/humanize/stream", summary="Stream Humanized Text (SSE)")
async def humanize_stream_endpoint(payload: HumanizeRequest) -> StreamingResponse:
    """Stream humanized text chunks via Server-Sent Events (SSE)."""
    if payload.text is None:
        raise HTTPException(status_code=422, detail="Field 'text' is required")
    if payload.mode not in ("budget", "deep"):
        raise HTTPException(status_code=422, detail=f"Invalid mode '{payload.mode}'. Must be 'budget' or 'deep'")

    client = get_client()

    async def event_generator():
        yield 'data: {"event": "start"}\n\n'
        if payload.text:
            async for chunk in client.humanize_stream(
                text=payload.text,
                mode=payload.mode,  # type: ignore[arg-type]
                tone=payload.tone,  # type: ignore[arg-type]
                reading_level=payload.reading_level,  # type: ignore[arg-type]
                preserve_markdown=payload.preserve_markdown,
            ):
                data_str = json.dumps({"chunk": chunk})
                yield f"data: {data_str}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
