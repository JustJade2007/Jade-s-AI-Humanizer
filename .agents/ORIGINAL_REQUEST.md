# Original User Request

## 2026-09-10T08:51:21Z

A zero-backend, client-side/local Python text humanizer library, CLI, and standalone REST API daemon that transforms AI-generated text into natural, human-sounding writing using Gemini Flash Lite with minimal token consumption and user-supplied API keys. Maintain a comprehensive README.md, CHANGELOG.md, and TODO.md in the repository root.

Working directory: c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer
Integrity mode: development

## Requirements

### R1. Python Library & Local REST API Daemon
- Provide a clean, importable Python library (`from humanizer import Humanizer`) with both synchronous (`humanize`) and asynchronous (`humanize_async`) interfaces.
- Provide a zero-configuration local HTTP daemon (`humanizer serve --port 8000`) exposing standard REST endpoints (`POST /v1/humanize`, `GET /health`) with OpenAPI/Swagger interactive docs at `/docs`.
- Support Server-Sent Events (SSE) streaming for real-time humanized text generation.
- Accept Gemini API key from environment variables (`GEMINI_API_KEY`) or direct constructor parameters with zero third-party telemetry or external proxy dependencies.
- Package and generate a standalone Windows executable (`humanizer.exe`) via PyInstaller so users without Python installed can launch the local API server with a single click.

### R2. Token-Minimized Humanization Engine
- **Tiered Modes:**
  - `budget` (default): Single-pass minimal token rewrite utilizing compact system instructions and local rule-based heuristics to minimize prompt token overhead.
  - `deep`: Multi-layered paraphrasing for maximum naturalness and detection evasion.
- **Style Presets:** Configurable `tone` (`neutral`, `casual`, `academic`, `professional`) and `reading_level`.
- **Quality & Vocabulary Guardrails:**
  - Automated post-processing verification ensuring grammatical correctness.
  - Natural, accessible human vocabulary avoiding archaic/rarely-used words and overused AI clichés (e.g., "delve", "tapestry", "in summary", "moreover") unless strictly required by technical context.

### R3. Structural & Markdown Document Chunking
- Automatically partition long texts (articles, multi-page papers) along semantic paragraph boundaries while preserving markdown structure (headers, lists, tables) and leaving code blocks completely untouched.

### R4. Documentation & Changelog
- Maintain an up-to-date, comprehensive `README.md` (installation, quickstart, Python library usage, local REST API usage, options reference).
- Maintain an up-to-date `CHANGELOG.md` documenting versions, additions, and updates.
- Maintain a `TODO.md` tracking active and upcoming features.

## Acceptance Criteria

### API & Packaging
- [ ] `from humanizer import Humanizer` functions cleanly in a sample script, executing both sync and async calls.
- [ ] `humanizer serve` starts a FastAPI/Uvicorn daemon locally and returns HTTP 200 on `GET /health` and valid JSON on `POST /v1/humanize`.
- [ ] SSE streaming endpoint returns valid chunked text stream without connection drops.
- [ ] Standalone `humanizer.exe` is built, successfully executes, and responds to local HTTP requests.

### Quality & Token Optimization
- [ ] Automated benchmark test demonstrates `budget` mode operates under strict token overhead thresholds (<100 prompt tokens overhead per request).
- [ ] Automated vocabulary audit scans output text and confirms 0 occurrences of banned AI buzzwords.
- [ ] Automated grammar verification test confirms all generated text contains no broken syntax or punctuation artifacts.
- [ ] Markdown formatting benchmark verifies code blocks, bulleted lists, and headers remain structurally identical to source text.

### Documentation
- [ ] `README.md` provides clear copy-paste code snippets for Python and cURL/REST endpoints.
- [ ] `CHANGELOG.md` records initial release details.
