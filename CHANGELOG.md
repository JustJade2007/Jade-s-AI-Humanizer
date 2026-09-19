# Changelog

All notable changes to **Jade''s AI Humanizer** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.2] - 2026-09-19

### Added
- **Plain-Language Anti-Jargon & Descriptive Deflation Engine (`thesaurus.py`, `prompt.py`, `client.py`)**:
  - Eliminates dramatic and escalating qualifiers (e.g., *"this adaptation directly addresses the escalating challenges"* &rarr; *"this change addresses the growing problems"*, *"escalating crisis"* &rarr; *"worsening crisis"*).
  - De-inflates textbook, academic, and environmental jargon into grounded human wording (e.g., *"conventional urban environments are heavily composed of impermeable surfaces that trigger flash flooding, trap solar radiation, and drive ambient temperatures upward"* &rarr; *"cities are largely covered in concrete and asphalt that cause flash flooding, trap heat, and drive up temperatures"*).
  - Eliminates clinical, geometric, and architectural over-descriptions of physical objects (e.g., *"retaining the essential rectangular geometry and expansive glass walls"* &rarr; *"keeping the basic rectangular shape and large glass walls"*).
  - Purges stiff Latinate filler words (e.g., *mitigate*, *exacerbate*, *commence*, *facilitate*, *ubiquitous*, *burgeoning*, *concomitant*, *salient*).
  - Integrated deflation rules seamlessly into sync and async Markdown chunk processing pipelines and streaming chunk accumulators.
  - Tuned `BUDGET_BASE_INSTRUCTION` to strictly preserve the <100 prompt token overhead threshold across multi-chunk documents while reinforcing plain-language directives.
  - Added unit test suite in `tests/unit/test_thesaurus.py`, bringing total passed tests to 301.
  - Re-compiled standalone `dist/humanizer.exe` executable via PyInstaller.

---

## [1.2.1] - 2026-09-14

### Fixed
- **API Key Handling & Graceful Fallback (`generator.py`, `routes.py`, `ui.py`)**:
  - Fixed `SyntaxError: Unexpected token 'I', "Internal S"... is not valid JSON` in the web UI when errors occur or when an API key fails. Responses are now consumed as raw text first before attempting JSON parsing, preventing unhandled syntax errors on plain-text HTTP 500 error pages.
  - Added global FastAPI exception handler in `src/humanizer/daemon/app.py` to ensure uncaught exceptions always return structured JSON responses rather than plain-text internal server error pages.
  - Sanitized API key inputs to automatically strip whitespace and wrapping quotation marks (`"`, `'`) pasted from configuration files or prompts.
  - Added fallback recovery in `GeminiGenerator`: when an API key is provided but Gemini endpoints are unreachable or rejected, it gracefully falls back to local heuristic paraphrasing while reporting offline status.
  - Rebuilt standalone `dist/humanizer.exe` executable with updated UI and error-resilient client.

### CI/CD & Publishing
- **PyPI Trusted Publishing (OIDC)**: Migrated `.github/workflows/python-publish.yml` to OIDC-based Trusted Publishing with `pypa/gh-action-pypi-publish@release/v1`. Configured job-scoped `id-token: write` permissions and `pypi` GitHub Environment pointing to package release URL, removing legacy static token dependency.
- **Automated Version Synchronization**: Added `packaging/sync_version.py` into the CI build pipeline to automatically harmonize package versions across `pyproject.toml` and `src/humanizer/__init__.py` from Git release tags and workflow dispatch inputs.
- **Publish Resilience (`skip-existing`)**: Enabled `skip-existing: true` and `verbose: true` to prevent workflow crashes when re-running workflows or releasing without overwriting immutable PyPI artifacts.

---

## [1.2.0] - 2026-09-11

### Added
- **Embedded Web UI & API Key Input (`src/humanizer/daemon/ui.py`, `routes.py`)**:
  - Added modern, responsive single-page Web UI served directly at `GET /` when launching the daemon or double-clicking `humanizer.exe`.
  - Added Gemini API Key input in the web interface header with visibility toggle, "Save Key" (saved to browser `localStorage`), and "Clear" buttons.
  - Implemented dynamic engine detection: checks `GET /health` and displays a live badge: `🟢 Online (Gemini Flash Lite)` when configured vs. `🟠 Offline (No API Key)` when running local heuristics.
  - Added explicit offline notice banner and 0 token billing indicator: in offline mode, it clearly informs the user that text was processed 100% locally with 0 API tokens billed.
  - Updated API contracts: `HumanizeRequest` accepts optional `api_key`, and `HumanizeResponse` provides `is_offline`, `engine`, and `api_tokens_used`.
  - Added custom SVG icon served at `GET /favicon.ico`.
  - Rebuilt standalone `dist/humanizer.exe` (22.5 MB) incorporating the updated web UI and offline detection.
  - Added automated E2E tests `test_f8_06_daemon_root_web_ui`, `test_f8_07_daemon_favicon`, and `test_f8_08_daemon_offline_detection_and_zero_tokens`, bringing test suite total to 294 passed tests.

---

## [1.1.0] - 2026-09-11

### Added
- **Thesaurus De-Flater & Purple Prose Filter (`src/humanizer/engine/thesaurus.py`)**:
  - Implemented comprehensive descriptor de-flating engine that strips pseudo-profound, melodramatic adjectives and flowery purple prose that characterize AI-generated text.
  - De-inflates phrases like *"forces a confrontation with the quiet gravity of"* -> *"makes you face a history mostly lost to"*, *"burdened with remembrance"* -> *"heavy with memory"*, *"emotional anchor in a commercialized environment"* -> *"sits right in the middle of all the busy stores and traffic"*, and *"silent contemplation"* -> *"standing completely still"*.
  - Added comprehensive common-usage replacements for physical things and feelings (e.g. *"palpable"* -> *"clear"*, *"visceral"* -> *"gut"*, *"effigy"* -> *"wooden figure"*, *"commercial sprawl"* -> *"busy stores and traffic"*).
  - Added full test suite in `tests/unit/test_thesaurus.py` bringing test coverage to 291 passing tests.
  - Added strict punctuation rule in grammar sanitizer eliminating all em-dashes (`—`) and replacing them with a space.
  - Updated `dist/humanizer.exe` standalone binary with embedded thesaurus filtering and em-dash removal.

---

## [1.0.0] - 2026-09-11

### Initial Release

#### Added
- **Core Paraphrasing Engine (`src/humanizer/client.py`, `src/humanizer/engine/`)**:
  - Full support for Google Gemini Flash Lite (`gemini-2.5-flash-lite` and `gemini-2.0-flash-lite`) via the official `google-genai` SDK.
  - Zero third-party telemetry, 100% local, client-side execution.
  - Built-in offline deterministic fallback engine when running without an API key or during network downtime.
  - Dual operational modes:
    - `budget`: Minimal-token prompt rewrite (<100 tokens overhead) for high throughput and ultra-low cost.
    - `deep`: Multi-pass paraphraser incorporating burstiness variation, perplexity shifts, contraction tuning, and middle-school vocabulary calibration.
  - Configurable style presets:
    - Tones: `neutral`, `casual`, `academic`, `professional`.
    - Reading levels: `general`, `middle_school`, `high_school`, `college`.

- **Quality Guardrails & Anti-Detection (`src/humanizer/engine/guardrails.py`)**:
  - Zero-tolerance AI buzzword and cliché removal catalog (*"delve into"*, *"tapestry of"*, *"testament to"*, *"in conclusion"*, *"moreover"*, *"foster"*, *"multifaceted"*, etc.) with case-preserving replacements.
  - Automated grammar and syntax sanitizer (punctuation spacing, double commas, capitalization corrections, duplicate word elimination).
  - List and quote indentation preservation ensuring nested structures remain intact.

- **Markdown & Code Invariance (`src/humanizer/parser/`)**:
  - Two-tier Markdown parser isolating fenced code blocks (` ``` ` and `~~~`) and GFM tables.
  - Token mask engine for inline code (`code`), math formulas (`$formula$`), and URLs/hyperlinks.
  - Currency protection preventing `$10` and `$50` from false math detection.
  - Semantic chunker supporting multi-page articles and oversized paragraphs.

- **Local REST Daemon & SSE Streaming (`src/humanizer/daemon/`)**:
  - FastAPI-powered local server with Uvicorn worker.
  - `GET /health` endpoint for daemon status and engine state.
  - `POST /v1/humanize` endpoint for synchronous JSON requests.
  - `POST /v1/humanize/stream` endpoint with Server-Sent Events (SSE) streaming for real-time humanization.
  - Interactive OpenAPI / Swagger UI at `/docs`.

- **CLI & Packaging (`src/humanizer/cli.py`, `packaging/build_exe.py`)**:
  - `humanizer serve` and `humanizer humanize` subcommands.
  - Standalone Windows executable `dist/humanizer.exe` bundled with PyInstaller.
  - One-click launch support (defaults to `serve` mode on double-click).

- **Automated Verification Suite (`tests/`)**:
  - 285 automated tests spanning unit, end-to-end (Tiers 1-4), adversarial stress tests, and token overhead benchmarks with 100% pass rate.
