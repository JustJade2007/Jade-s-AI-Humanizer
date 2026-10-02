# Security Policy

## Overview

**Jade's AI Humanizer** is engineered from the ground up as a **100% client-side, local-first** application. When using the CLI, desktop executable, or local REST daemon:
- **Zero Third-Party Telemetry:** No user text, prompts, logs, or metrics are transmitted to any intermediate server or proxy.
- **Direct Upstream Requests:** When an API key is configured, requests are made directly between your local machine and Google's official Gemini API endpoints via HTTPS.
- **Offline Deterministic Fallback:** When no API key is provided, humanization is computed 100% locally on your machine using deterministic NLP heuristics and guardrails, without any internet connection.

---

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.2.x   | :white_check_mark: |
| < 1.2.0 | :x:                |

---

## Security Architecture & Defenses

### 1. Localhost CORS Isolation
The built-in FastAPI daemon binds exclusively to local interfaces by default (`127.0.0.1`). Cross-Origin Resource Sharing (CORS) is strictly restricted to local origins (`localhost` and `127.0.0.1` on any port) with `allow_credentials=False` to prevent malicious third-party websites visited in a browser from issuing unauthorized cross-origin requests to your local daemon. Custom origins can be provided via the `HUMANIZER_CORS_ORIGINS` environment variable.

### 2. Defensive HTTP Headers
All daemon responses include the following security headers:
- `X-Content-Type-Options: nosniff` (prevents MIME-type sniffing)
- `X-Frame-Options: SAMEORIGIN` (prevents clickjacking attacks)
- `Referrer-Policy: strict-origin-when-cross-origin` (prevents sensitive path and query leakage)
- `Content-Security-Policy: default-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' http://127.0.0.1:* http://localhost:*`

### 3. API Key Protection & Secret Redaction
- In the Web UI, API keys are kept strictly in browser client-side `localStorage` and sent via encrypted HTTPS headers directly.
- The daemon accepts API keys via `X-API-Key` or `Authorization: Bearer` headers to avoid credential exposure in access logs and URL histories.
- The `sanitize_sensitive_string` utility automatically scrubs any Google API keys, bearer tokens, or query parameter keys from error messages and exception traces before responses are returned to the client.

### 4. Denial of Service & ReDoS Protection
- An explicit character limit (`max_length=100,000`) is enforced on input payloads to protect against memory exhaustion.
- All regexes in the guardrail and readability engines use linear character scans and negated character classes to prevent catastrophic polynomial backtracking (ReDoS).

---

## Reporting a Vulnerability

If you discover a security vulnerability or potential privacy issue in Jade's AI Humanizer, please report it responsibly:
1. Do **not** open a public GitHub issue.
2. Email the repository maintainer directly at **jacobhite2007@gmail.com** or report through GitHub Private Vulnerability Reporting under the repository's **Security** tab.
3. Include a description of the vulnerability, steps to reproduce, and any relevant proof-of-concept.

All security reports are acknowledged within 48 hours, and fixes are prioritized for immediate patch release.
