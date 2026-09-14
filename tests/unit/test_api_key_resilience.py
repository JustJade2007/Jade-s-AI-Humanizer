"""Tests for API key error resilience and graceful offline fallback in Jade's AI Humanizer."""

import pytest
from fastapi.testclient import TestClient

from humanizer.daemon.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_check_with_quoted_key(client):
    """Verify health endpoint strips quotes and whitespace from API key."""
    res = client.get('/health?api_key="my_key"')
    assert res.status_code == 200
    data = res.json()
    assert data["api_key_configured"] is True
    assert data["is_offline"] is False


def test_humanize_graceful_fallback_on_invalid_api_key(client):
    """Verify /v1/humanize gracefully falls back to offline heuristic when API key fails."""
    payload = {
        "text": "We must delve into the tapestry of concepts.",
        "mode": "budget",
        "tone": "neutral",
        "reading_level": "general",
        "preserve_markdown": True,
        "api_key": ' "invalid_key_12345" ',
    }
    res = client.post("/v1/humanize", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_offline"] is True
    assert data["engine"] == "gemini-flash-lite (offline)"
    assert data["api_tokens_used"] == 0
    assert "delve into" not in data["humanized_text"]
    assert "tapestry of" not in data["humanized_text"]


def test_stream_graceful_fallback_on_invalid_api_key(client):
    """Verify /v1/humanize/stream falls back gracefully when API key fails."""
    payload = {
        "text": "We delve into the concepts.",
        "mode": "budget",
        "tone": "neutral",
        "reading_level": "general",
        "preserve_markdown": True,
        "api_key": "bad_key",
    }
    res = client.post("/v1/humanize/stream", json=payload)
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]
    assert '{"event": "start"}' in res.text
    assert "[DONE]" in res.text
