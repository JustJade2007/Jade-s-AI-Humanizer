# TODO & Roadmap

Tracking completed deliverables and upcoming feature milestones for **Jade''s AI Humanizer**.

---

## Completed (v1.0.0)

- [x] **Core Architecture & Client Library**
  - [x] Universal `Humanizer` client (`humanize`, `humanize_async`, `humanize_stream`, `humanize_stream_sync`).
  - [x] Official `google-genai` SDK integration for Gemini Flash Lite (`gemini-2.5-flash-lite` / `gemini-2.0-flash-lite`).
  - [x] Offline deterministic fallback engine for 100% offline usage.
  - [x] Minimal prompt token consumption (<100 tokens overhead in Budget mode).
  - [x] Deep mode with burstiness variation, perplexity shifts, and contraction expansion.

- [x] **Markdown & Document Parsing**
  - [x] Fenced code block preservation (both backtick and tilde fences).
  - [x] GFM table preservation with alignment markers and embedded pipes.
  - [x] Inline code, URL, autolink, and LaTeX math masking.
  - [x] Semantic paragraph chunking with oversized paragraph splitting.

- [x] **Guardrails & Quality Assurance**
  - [x] 0-tolerance AI clichés and buzzword replacement dictionary.
  - [x] Case-preserving buzzword substitution.
  - [x] **Thesaurus De-Flater & Purple Prose Filter** (stripping pseudo-profound descriptors and melodrama).
  - [x] Syntax, punctuation, and reduplication grammar sanitizer.
  - [x] Flesch Reading Ease and Flesch-Kincaid Grade Level calculators.

- [x] **Local REST Daemon & Streaming**
  - [x] FastAPI local HTTP server with Uvicorn.
  - [x] `GET /health` diagnostic endpoint.
  - [x] `POST /v1/humanize` synchronous endpoint.
  - [x] `POST /v1/humanize/stream` Server-Sent Events (SSE) streaming endpoint.
  - [x] Interactive OpenAPI / Swagger UI at `/docs`.

- [x] **CLI & Standalone Executable**
  - [x] CLI entry point `humanizer` with `serve` and `humanize` subcommands.
  - [x] Standalone Windows executable `dist/humanizer.exe` compiled via PyInstaller.
  - [x] Automatic zero-argument fallback to `serve` for single-click Windows launching.

- [x] **Test & Documentation Coverage**
  - [x] 285 passing tests across unit, e2e, adversarial stress, and token overhead benchmarks.
  - [x] Comprehensive `README.md` with copy-paste code snippets.
  - [x] Versioned `CHANGELOG.md`.

---

## Future Roadmap & Backlog

- [ ] **Desktop Tray & GUI**
  - [ ] Optional system tray icon (Windows / macOS) to start, stop, and monitor the local REST daemon.
  - [ ] Clipboard watcher mode (auto-humanize text copied to clipboard on keyboard hotkey).

- [ ] **Expanded Language Support**
  - [ ] Multi-lingual buzzword dictionaries (Spanish, French, German, Japanese, Chinese).
  - [ ] Language-specific readability formulas (Flesch-Szigriszt for Spanish, Wiener Sachtextformel for German).

- [ ] **Additional Provider Integrations (Zero-Backend Local First)**
  - [ ] Local Ollama / vLLM integration option (e.g. `llama3.2`, `mistral`, `gemma-2-2b-it`).
  - [ ] Anthropic Claude Haiku and OpenAI GPT-4o-mini provider connectors with identical prompt budget constraints.

- [ ] **Batch Processing Utility**
  - [ ] Directory-wide batch document humanization via CLI (`humanizer batch --input-dir docs/ --output-dir out/`).
  - [ ] PDF and docx input/output parsers preserving native document styling.
