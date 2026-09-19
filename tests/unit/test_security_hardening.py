"""Unit tests for security hardening and vulnerability remediation in Jade's AI Humanizer."""

import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from humanizer.daemon.app import create_app, sanitize_sensitive_string
from humanizer.daemon.routes import extract_api_key
from humanizer.engine.generator import GeminiGenerator


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_cors_restrictions_and_credentials(client):
    """Verify CORS permits localhost origins without credentials, and restricts arbitrary origins."""
    # Localhost origin should receive allow origin header
    res_local = client.options(
        "/v1/humanize",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_local.status_code == 200
    assert res_local.headers.get("access-control-allow-origin") == "http://localhost:8000"
    assert res_local.headers.get("access-control-allow-credentials") is None

    # Untrusted external origin must not be allowed
    res_external = client.options(
        "/v1/humanize",
        headers={
            "Origin": "https://malicious-attacker-site.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert res_external.headers.get("access-control-allow-origin") != "https://malicious-attacker-site.com"


def test_defensive_security_headers_present(client):
    """Verify required HTTP security headers are attached to responses."""
    res = client.get("/")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "SAMEORIGIN"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "default-src 'self'" in res.headers["content-security-policy"]


def test_input_payload_max_length_validation(client):
    """Verify text payloads exceeding 100,000 characters trigger HTTP 422."""
    oversized_text = "A" * 100_001
    payload = {
        "text": oversized_text,
        "mode": "budget",
    }
    res = client.post("/v1/humanize", json=payload)
    assert res.status_code == 422
    data = res.json()
    assert any("at most 100000 characters" in str(err) or "max_length" in str(err) or "length" in str(err) for err in data.get("detail", []))


def test_header_based_api_key_authentication(client):
    """Verify API keys are safely accepted via X-API-Key or Authorization headers."""
    # Test X-API-Key on /health
    res_x_key = client.get("/health", headers={"X-API-Key": "test_x_api_key_12345"})
    assert res_x_key.status_code == 200
    data = res_x_key.json()
    assert data["api_key_configured"] is True
    assert data["is_offline"] is False

    # Test Authorization Bearer on /health
    res_auth = client.get("/health", headers={"Authorization": "Bearer test_bearer_key_67890"})
    assert res_auth.status_code == 200
    data = res_auth.json()
    assert data["api_key_configured"] is True
    assert data["is_offline"] is False

    # Backward compatibility: legacy query parameter still works
    res_query = client.get("/health?api_key=legacy_param_key")
    assert res_query.status_code == 200
    assert res_query.json()["api_key_configured"] is True


def test_header_based_api_key_on_humanize(client):
    """Verify /v1/humanize accepts X-API-Key and Authorization headers."""
    payload = {
        "text": "The quick brown fox jumps over the lazy dog.",
        "mode": "budget",
    }
    res = client.post(
        "/v1/humanize",
        json=payload,
        headers={"X-API-Key": "header_key_abc"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["humanized_text"] != ""


def test_sanitize_sensitive_string_redaction():
    """Verify sensitive patterns such as Google API keys and query strings are thoroughly redacted."""
    raw_error = "Error connecting to https://generativelanguage.googleapis.com/v1beta/models/gemini-flash:generateContent?key=AIzaSyA1234567890abcdefghijklmnopqrstuv"
    sanitized = sanitize_sensitive_string(raw_error)
    assert "AIzaSyA1234567890" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized

    raw_header_err = "Failed with x-goog-api-key: secret_1234567890 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized_header = sanitize_sensitive_string(raw_header_err)
    assert "secret_1234567890" not in sanitized_header
    assert "eyJhbGci" not in sanitized_header
    assert "[REDACTED_API_KEY]" in sanitized_header
    assert "[REDACTED]" in sanitized_header


def test_upstream_rest_generator_headers():
    """Verify direct REST fallback transmits api_key in x-goog-api-key header and not in query string."""
    fake_key = "AIzaSyTestKey12345"
    generator = GeminiGenerator(api_key=fake_key, mock_mode=False)
    generator._client = None  # Force REST fallback

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Humanized test output."}]}}],
        "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
    }

    with patch("requests.post", return_value=mock_resp) as mock_post:
        out, usage = generator._call_gemini_sync(
            model_name="gemini-2.5-flash-lite",
            prompt="Hello world",
            system_instruction="Be natural",
            temperature=0.7,
        )
        assert out == "Humanized test output."
        assert mock_post.called
        call_args, call_kwargs = mock_post.call_args
        called_url = call_args[0]
        called_headers = call_kwargs.get("headers", {})

        # Key must NOT be in URL query
        assert "?key=" not in called_url
        assert fake_key not in called_url
        # Key MUST be in headers
        assert called_headers.get("x-goog-api-key") == fake_key
