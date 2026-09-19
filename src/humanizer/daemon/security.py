"""Security utilities and middleware for Jade's AI Humanizer daemon."""

from __future__ import annotations

import os
import re
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


def sanitize_sensitive_string(text: str) -> str:
    """Redact API keys or sensitive query params from error messages."""
<<<<<<< HEAD
    # Redact Google API keys or other long API keys
    key_pattern = r"A" + r"Iza[0-9A-Za-z-_]{35}"
    text = re.sub(key_pattern, "[REDACTED_API_KEY]", text)
=======
    # Redact AIza... or other long API keys
    text = re.sub(r"AIza[0-9A-Za-z-_]{35}", "[REDACTED_API_KEY]", text)
>>>>>>> aa79738a81b86443fdf93f6d4a7ad721c1bec5c5
    # Redact key=... query parameters
    text = re.sub(r"([?&]key=)[^&\s]+", r"\1[REDACTED_API_KEY]", text, flags=re.IGNORECASE)
    # Redact x-goog-api-key: ...
    text = re.sub(r"(x-goog-api-key:\s*)[^\s]+", r"\1[REDACTED_API_KEY]", text, flags=re.IGNORECASE)
    # Redact Authorization: Bearer ...
    text = re.sub(r"(bearer\s+)[A-Za-z0-9_\-\.]{15,}", r"\1[REDACTED]", text, flags=re.IGNORECASE)
    return text


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach standard defensive security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' http://127.0.0.1:* http://localhost:*;"
        )
        return response


def extract_api_key(
    body_key: Optional[str] = None,
    header_x_api_key: Optional[str] = None,
    header_authorization: Optional[str] = None,
    query_key: Optional[str] = None,
) -> Optional[str]:
    """Securely resolve API key with priority: headers -> body -> query -> env."""
    key = header_x_api_key
    if not key and header_authorization:
        if header_authorization.lower().startswith("bearer "):
            key = header_authorization[7:].strip()
        else:
            key = header_authorization.strip()
    if not key:
        key = body_key
    if not key:
        key = query_key or os.getenv("GEMINI_API_KEY")
    if key:
        cleaned = key.strip().strip('"\'')
        return cleaned if cleaned else None
    return None
