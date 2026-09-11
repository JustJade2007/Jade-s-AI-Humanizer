# Project: Jade's AI Humanizer

## Architecture
Jade's AI Humanizer is a zero-backend, client-side/local Python text humanizer library, CLI, and standalone REST API daemon powered by Gemini Flash Lite (`gemini-2.5-flash-lite` / `gemini-2.0-flash-lite`).

### System Decomposition
```
[User / Client]
       │
       ├── Python Library: `from humanizer import Humanizer` (sync, async, stream)
       ├── CLI: `humanizer serve --port 8000`, `humanizer humanize`
       └── Standalone Executable: `humanizer.exe` (PyInstaller Windows standalone)
              │
              ▼
    [FastAPI / Uvicorn Daemon]
       ├── GET /health
       ├── POST /v1/humanize (REST JSON)
       ├── POST /v1/humanize/stream (SSE Streaming)
       └── GET /docs (Swagger OpenAPI UI)
              │
              ▼
    [Markdown & Structural Chunker]
       ├── Pure-Python block tokenizer (Code, Tables, Headers, Lists, Paragraphs)
       ├── Inline token masking (`⟦CODE_X⟧`, `⟦URL_X⟧`)
       └── 100% protection for code blocks and markdown tables
              │
              ▼
    [Token-Minimized Engine]
       ├── Budget mode (<100 tokens overhead, compact system prompt)
       ├── Deep mode (multi-pass burstiness & perplexity shifting)
       ├── Style presets (neutral, casual, academic, professional)
       ├── Reading level scaling (middle_school to college)
       └── Offline mock client & token simulator
              │
              ▼
    [Quality Guardrails & Post-Processing]
       ├── 0-tolerance banned AI buzzwords regex audit (delve, tapestry, moreover, etc.)
       ├── Heuristic grammar & punctuation sanitizer
       └── Readability scorer (Flesch-Kincaid)
```

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| F1 | Python Library Interface | `from humanizer import Humanizer`, sync `humanize()`, async `humanize_async()`, streaming generator `humanize_stream()` | M1 | ORIGINAL_REQUEST §R1 |
| F2 | Gemini Client & Mock Engine | `google-genai` client integration, API key handling (env/param), offline deterministic mock & token simulator | M1 | ORIGINAL_REQUEST §R1 |
| F3 | Budget Mode Engine | Minimal prompt token overhead (<100 tokens overhead), single-pass rewrite | M1 | ORIGINAL_REQUEST §R2 |
| F4 | Deep Mode Engine | Multi-layered paraphrasing, burstiness variation, perplexity shifting, detection evasion | M1 | ORIGINAL_REQUEST §R2 |
| F5 | Style Presets & Reading Levels | `tone` (`neutral`, `casual`, `academic`, `professional`) & `reading_level` with Flesch-Kincaid validation | M1 | ORIGINAL_REQUEST §R2 |
| F6 | Quality Guardrails & Buzzword Audit | 0 banned AI buzzwords check with auto-replacement, automated syntax/grammar verification | M1 | ORIGINAL_REQUEST §R2 |
| F7 | Structural & Markdown Chunker | Two-tier block parser preserving code blocks, tables, headers, lists; inline code/URL masking | M2 | ORIGINAL_REQUEST §R3 |
| F8 | CLI & REST API Daemon | `humanizer serve --port 8000`, FastAPI daemon, `/health`, `/v1/humanize`, interactive docs `/docs` | M3 | ORIGINAL_REQUEST §R1 |
| F9 | SSE Streaming Endpoint | Real-time SSE streaming via native `StreamingResponse` (`POST /v1/humanize/stream`) | M3 | ORIGINAL_REQUEST §R1 |
| F10 | Standalone Windows Executable | `humanizer.exe` packaging via PyInstaller, single-click server auto-launch, `freeze_support` | M4 | ORIGINAL_REQUEST §R1, User Global Rule |
| F11 | Documentation & Global Rules | `README.md`, `CHANGELOG.md`, `TODO.md` in repository root with copy-paste snippets and changelog | M4 | ORIGINAL_REQUEST §R4, User Global Rule |
| F12 | Comprehensive Test Suite & Benchmarks | Full test suite across Tiers 1-4, <100 token benchmark, vocabulary audit test, markdown preservation test | M5 | ORIGINAL_REQUEST §Acceptance Criteria |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Core Engine & Guardrails | F1, F2, F3, F4, F5, F6: Python library class, Gemini client & mock, budget/deep modes, style presets, quality/buzzword guardrails | none | DONE |
| M2 | Markdown & Structural Chunking | F7: Markdown tokenizer, block separator, table/code block protection, inline masking, chunk reconstructor | M1 | DONE |
| M3 | CLI, REST API Daemon & SSE | F8, F9: FastAPI daemon, Uvicorn ASGI server, `/health`, `/v1/humanize`, SSE streaming `/v1/humanize/stream`, CLI commands | M1, M2 | PLANNED |
| M4 | Packaging & Documentation | F10, F11: Standalone `humanizer.exe` build via PyInstaller, root `README.md`, `CHANGELOG.md`, `TODO.md` | M1, M2, M3 | PLANNED |
| M5 | E2E Acceptance & Adversarial Hardening | F12: 100% E2E test suite pass (Tiers 1-4), benchmarks (<100 tokens, 0 buzzwords, markdown integrity), Tier 5 adversarial testing | M1, M2, M3, M4 | PLANNED |

## Interface Contracts

### 1. `Humanizer` Core Interface (`src/humanizer/client.py`)
```python
class Humanizer:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.0-flash-lite",
        mock_mode: bool = False,
    ): ...

    def humanize(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> HumanizeResult: ...

    async def humanize_async(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> HumanizeResult: ...

    async def humanize_stream(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> AsyncIterator[str]: ...
```

### 2. `HumanizeResult` Data Contract (`src/humanizer/models.py`)
```python
@dataclass
class HumanizeResult:
    text: str
    original_text: str
    mode: str
    tone: str
    reading_level: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    buzzwords_replaced: list[str]
    flesch_reading_ease: float
```

### 3. Markdown Parser Interface (`src/humanizer/parser/markdown.py`)
```python
class MarkdownDocument:
    def __init__(self, raw_markdown: str): ...
    def extract_chunks(self) -> list[DocumentChunk]: ...
    def reconstruct(self, humanized_chunks: list[str]) -> str: ...
```

### 4. REST API Schema (`src/humanizer/daemon/routes.py`)
- `GET /health` -> `{"status": "ok", "version": "0.1.0", "model": "gemini-2.5-flash-lite"}`
- `POST /v1/humanize` -> Request: `{"text": str, "mode": str, "tone": str, "reading_level": str, "preserve_markdown": bool}` -> Response: `HumanizeResponse` JSON
- `POST /v1/humanize/stream` -> SSE Stream of `data: {"chunk": "..."}\n\n` ending with `data: [DONE]\n\n`

## Code Layout
```
Jade's AI Humanizer/
├── src/
│   └── humanizer/
│       ├── __init__.py          # Exports Humanizer, HumanizeResult
│       ├── client.py            # Main Humanizer class (sync & async)
│       ├── models.py            # Pydantic & dataclass schemas
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── prompt.py        # Token-minimized system & style prompts (<100 tokens)
│       │   ├── generator.py     # Gemini client execution & retry logic
│       │   ├── deep.py          # Multi-layered deep paraphraser
│       │   ├── guardrails.py    # Banned buzzwords audit & grammar sanitizer
│       │   └── readability.py   # Pure-Python Flesch-Kincaid scorer
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── markdown.py      # Structural markdown parser & chunker
│       │   └── mask.py          # Inline code/URL token mask
│       ├── daemon/
│       │   ├── __init__.py
│       │   ├── app.py           # FastAPI application definition
│       │   └── routes.py        # REST & SSE streaming endpoints
│       └── cli.py               # Click/argparse CLI entry point (`humanizer serve`)
├── packaging/
│   ├── entrypoint.py            # One-click desktop launcher with freeze_support
│   ├── build_exe.py             # PyInstaller automated build script
│   └── humanizer.spec           # Reproducible PyInstaller specification
├── tests/
│   ├── e2e/                     # E2E test suite (Tiers 1-4)
│   │   ├── conftest.py
│   │   ├── test_tier1_feature_coverage.py
│   │   ├── test_tier2_boundaries.py
│   │   ├── test_tier3_cross_feature.py
│   │   └── test_tier4_real_world.py
│   ├── unit/                    # Unit tests per module
│   │   ├── test_engine.py
│   │   ├── test_guardrails.py
│   │   ├── test_markdown_parser.py
│   │   └── test_api.py
│   └── benchmarks/
│       ├── test_token_overhead.py  # Strict verification <100 overhead tokens
│       └── test_vocabulary_audit.py # Strict verification 0 buzzwords
├── dist/
│   └── humanizer.exe            # Windows standalone executable
├── pyproject.toml               # Project metadata and dependencies
├── README.md                    # Comprehensive documentation
├── CHANGELOG.md                 # Project version history
└── TODO.md                      # Feature backlog & upcoming items
```
