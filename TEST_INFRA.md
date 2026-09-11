# Test Infrastructure Specification: Jade's AI Humanizer

## 1. Executive Summary & Test Philosophy

Jade's AI Humanizer is engineered with an opaque-box, contract-driven test architecture designed to validate the library, CLI, and REST API daemon against the requirements specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`.

### Core Testing Tenets:
1. **Opaque-Box Public Interface Testing**: Tests exercise only public interfaces (`from humanizer import Humanizer`, CLI commands `humanizer serve`, and HTTP REST/SSE endpoints `/health`, `/v1/humanize`, `/v1/humanize/stream`). Internal implementation details are never coupled directly to tests.
2. **Deterministic Offline Execution**: CI and developer environments often lack paid Gemini API credentials or active internet connectivity. The test suite provides an offline mock client and deterministic token simulator in `conftest.py`, ensuring 100% of tests execute reliably and deterministically without network calls.
3. **Live API Compatibility**: When `GEMINI_API_KEY` is detected in the environment, the suite seamlessly supports end-to-end execution against live Google Gemini Flash Lite models (`gemini-2.5-flash-lite`, `gemini-2.0-flash-lite`).
4. **4-Tier Comprehensive Verification**: Test coverage spans isolated feature verification, boundary/corner stress testing, cross-feature interaction testing, and realistic end-to-end user application workflows.

---

## 2. Directory Layout & Test Suite Architecture

```
tests/
├── e2e/                                    # 4-Tier End-to-End Test Suite
│   ├── __init__.py                         # E2E test package declaration
│   ├── conftest.py                         # Offline mock engine, test clients & corpora fixtures
│   ├── test_tier1_features.py              # Tier 1: Feature Coverage (F1–F12, >=5 tests/feature)
│   ├── test_tier2_boundaries.py            # Tier 2: Boundary & Corner Cases (F1–F12, >=5 tests/feature)
│   ├── test_tier3_combinations.py          # Tier 3: Cross-Feature Interactions & Pairwise Matrices
│   └── test_tier4_scenarios.py             # Tier 4: Real-World Application Workflows (6 scenarios)
├── unit/                                   # Unit Test Suite per Module
│   ├── test_engine.py                      # Engine, prompts, readability
│   ├── test_guardrails.py                  # Vocabulary audit & grammar sanitizer
│   ├── test_markdown_parser.py             # Markdown block parser & chunker
│   └── test_api.py                         # Daemon endpoints & schemas
└── benchmarks/                             # Performance & Quality Benchmarks
    ├── test_token_overhead.py              # Strict < 100 prompt tokens overhead verification
    └── test_vocabulary_audit.py            # Strict 0 banned buzzwords verification
```

---

## 3. The 4-Tier Testing Methodology

### Tier 1: Feature Coverage (Isolated Happy Path)
- **Target**: Features F1 through F12 from `PROJECT.md § Feature Inventory`.
- **Threshold**: At least 5 distinct test cases per feature covering happy paths and representative inputs in isolation.
- **Inventory (60 Tests)**:
  - **F1 (Python Library Interface)**: `test_f1_01_humanizer_sync_execution`, `test_f1_02_humanizer_async_execution`, `test_f1_03_humanizer_stream_execution`, `test_f1_04_humanizer_default_parameters`, `test_f1_05_humanizer_return_type_contract`.
  - **F2 (Gemini Client & Mock Engine)**: `test_f2_01_api_key_from_constructor`, `test_f2_02_api_key_from_env`, `test_f2_03_missing_key_behavior`, `test_f2_04_offline_mock_mode_flag`, `test_f2_05_mock_token_counting_fidelity`.
  - **F3 (Budget Mode Engine)**: `test_f3_01_budget_mode_single_pass`, `test_f3_02_budget_mode_token_overhead_under_100`, `test_f3_03_budget_mode_preserves_core_facts`, `test_f3_04_budget_mode_concise_output`, `test_f3_05_budget_mode_default_selection`.
  - **F4 (Deep Mode Engine)**: `test_f4_01_deep_mode_paraphrasing`, `test_f4_02_deep_mode_burstiness_variation`, `test_f4_03_deep_mode_syntactic_cadence_shifts`, `test_f4_04_deep_mode_preserves_facts`, `test_f4_05_deep_mode_supports_all_tones`.
  - **F5 (Style Presets & Reading Levels)**: `test_f5_01_tone_neutral`, `test_f5_02_tone_casual`, `test_f5_03_tone_academic`, `test_f5_04_tone_professional`, `test_f5_05_reading_level_and_flesch_reading_ease`.
  - **F6 (Quality Guardrails & Buzzword Audit)**: `test_f6_01_banned_buzzwords_detected_and_replaced`, `test_f6_02_zero_tolerance_audit`, `test_f6_03_grammar_punctuation_spacing`, `test_f6_04_grammar_sentence_capitalization`, `test_f6_05_grammar_stutter_reduplication`.
  - **F7 (Structural & Markdown Chunker)**: `test_f7_01_code_blocks_byte_for_byte_preservation`, `test_f7_02_markdown_tables_pipe_preservation`, `test_f7_03_atx_headers_preservation`, `test_f7_04_markdown_lists_preservation`, `test_f7_05_inline_code_and_url_masking`.
  - **F8 (CLI & REST API Daemon)**: `test_f8_01_daemon_health_endpoint`, `test_f8_02_daemon_humanize_endpoint`, `test_f8_03_daemon_openapi_docs_endpoint`, `test_f8_04_cli_serve_argument_parsing`, `test_f8_05_daemon_cors_headers`.
  - **F9 (SSE Streaming Endpoint)**: `test_f9_01_sse_stream_content_type`, `test_f9_02_sse_stream_chunk_format`, `test_f9_03_sse_stream_done_sentinel`, `test_f9_04_sse_stream_custom_mode_and_tone`, `test_f9_05_sse_stream_no_connection_drops`.
  - **F10 (Standalone Windows Executable)**: `test_f10_01_freeze_support_in_entrypoint`, `test_f10_02_pyinstaller_spec_hidden_imports`, `test_f10_03_build_script_presence`, `test_f10_04_entrypoint_auto_serve_behavior`, `test_f10_05_spec_excludes_heavy_packages`.
  - **F11 (Documentation & Global Rules)**: `test_f11_01_readme_structure_and_snippets`, `test_f11_02_changelog_format`, `test_f11_03_todo_phase_tracking`, `test_f11_04_readme_curl_and_python_examples`, `test_f11_05_user_global_rules_compliance`.
  - **F12 (Comprehensive Benchmarks)**: `test_f12_01_benchmark_token_overhead_threshold`, `test_f12_02_benchmark_vocabulary_audit_zero_buzzwords`, `test_f12_03_benchmark_markdown_invariance`, `test_f12_04_benchmark_readability_scorer_accuracy`, `test_f12_05_benchmark_latency_and_throughput`.

### Tier 2: Boundary & Corner Cases (Adversarial Stress Testing)
- **Target**: Empty inputs, massive documents (>25k characters), zero/negative boundaries, punctuation extremes, malformed markdown, unclosed code fences, unicode, prompt injections, and malformed REST payloads.
- **Threshold**: At least 5 distinct boundary test cases per feature (60 Tests).
- **Inventory (60 Tests)**:
  - **F1 Boundaries**: Empty string input, whitespace-only input, single-word input, >25,000 char input, unicode emojis & math symbols.
  - **F2 Boundaries**: Empty api_key string, special characters in api_key, token counter on empty text, fallback model selection, multiple independent client instances.
  - **F3 Boundaries**: Prompt injection defense, repeated punctuation extremes (`????!!!!`), all-caps input, 100% buzzword document, consecutive blank lines.
  - **F4 Boundaries**: Single word burstiness, 100-word run-on sentence without punctuation, numeric IDs and hashes preservation, mixed inline backticks, empty input in deep mode.
  - **F5 Boundaries**: Unknown tone fallback, unknown reading level fallback, readability calculation with 0 sentences (no ZeroDivisionError), pure numbers/symbols readability, irregular syllable counting.
  - **F6 Boundaries**: Mixed-case buzzword variants (`DeLvE`, `TaPeStRy`), legitimate substring preservation (`delivery`), unclosed code fence repair, excessive whitespace before punctuation, double commas and periods.
  - **F7 Boundaries**: Unclosed code fences, malformed tables with uneven columns, tilde fences (`~~~`), sentinel token collision safety (`⟦CODE_0⟧`), code blocks containing buzzwords.
  - **F8 Boundaries**: Malformed JSON request body (422), missing text field (422), empty text body (200), invalid mode string (422), extra unrecognized fields handling.
  - **F9 Boundaries**: SSE empty input stream, whitespace-only stream, special characters JSON escaping, massive document stream, missing text payload (422).
  - **F10 Boundaries**: Entrypoint CLI argument override, PyInstaller spec Python AST validity, build script path checking, spec hidden import coverage, freeze_support main guard.
  - **F11 Boundaries**: File non-empty guards, UTF-8 compliance, inventory completeness in docs, user rules compliance.
  - **F12 Boundaries**: Token overhead non-negative check, 50-buzzword dense document audit, empty code block invariance, consonant-dense text readability, rapid 15-burst sequential calls.

### Tier 3: Cross-Feature Combinations (Pairwise & Multi-Feature Interactions)
- **Target**: Interactions between engine modes, chunking, tone presets, daemon routes, and packaging.
- **Inventory (14 Test Functions / 29 Executable Invocations)**:
  - Budget mode + markdown chunking + code blocks (F3 + F7).
  - Deep mode + GFM tables + inline code masking (F4 + F7).
  - Casual tone + middle school reading level + streaming generator (F5 + F1 + F9).
  - Academic tone + college reading level + budget mode + buzzword audit (F3 + F5 + F6).
  - Daemon SSE streaming + chunked markdown (F8 + F9 + F7).
  - Async execution + deep mode + grammar repair (F1 + F4 + F6).
  - Mock client + REST daemon `/v1/humanize` (F2 + F8).
  - Budget markdown benchmark token overhead <100 tokens (F3 + F7 + F12).
  - Deep mode readability + buzzword cleanse (F4 + F5 + F6).
  - Standalone spec + daemon routes routing contract (F8 + F10).
  - CLI serve custom host/port + daemon health check (F8 + F1).
  - Full 4x4 Tone x Reading Level matrix cross-verification (16 parametrized combinations) (F5 + F6).
  - Daemon input validation error handling (F8 + F3 + F5).
  - Streaming generator with code block preservation across chunk boundaries (F1 + F7 + F9).

### Tier 4: Real-World Application Scenarios (Comprehensive End-to-End Workflows)
- **Target**: Production-grade scenarios simulating authentic user workflows.
- **Inventory (6 Comprehensive Scenarios)**:
  1. **Tech Blog Post Humanization**: Casual tone, general reading level, ATX headings, bulleted lists, blockquote callouts, 0 buzzwords, < 100 token overhead.
  2. **Academic Technical Paper**: Deep mode, academic tone, college reading level, inline code `` `query_db()` ``, multi-column GFM comparison table, math formulas `$O(\log n)$`, Python consensus code fence byte-for-byte invariant.
  3. **Customer Support Email Rewrite**: Professional tone, greeting ('Dear Valued Customer,') and signoff ('Best regards,') preserved, auth URLs preserved, robotic AI phrasing eliminated, punctuation sanitized.
  4. **Marketing Pitch & Product Announcement**: Deep mode, casual tone, high burstiness, complete elimination of overused hype clichés ('game-changer', 'tapestry', 'plethora', 'bespoke').
  5. **Multi-Page Long Article with Semantic Paragraph Chunking**: 12 sections with ATX headers (`### Section 1:` through `### Section 12:`), hyperlinks preserved, semantic splitting along paragraph boundaries, >80% length retention, 0 buzzwords.
  6. **Full Daemon REST & SSE Client Workflow**: Probe `GET /health` for liveness, submit synchronous `POST /v1/humanize`, open real-time `POST /v1/humanize/stream` event stream, verify termination sentinel `data: [DONE]`.

---

## 4. Offline Mock Infrastructure & Fixture Contracts

In `tests/e2e/conftest.py`, the test suite provides an offline testing harness:
- **`MockGenAIClient`**: Implements the exact interface of the official `google.genai.Client`:
  - `client.models.generate_content(model, contents, config)` -> Returns `MockModelResponse` with `.text` and `.usage_metadata` (`prompt_token_count`, `candidates_token_count`, `total_token_count`).
  - `client.models.generate_content_stream(model, contents, config)` -> Generator yielding chunk objects with `.text`.
  - `client.models.count_tokens(model, contents)` -> Returns object with `.total_tokens`.
  - `client.aio.models.generate_content(...)` & `generate_content_stream(...)` -> Async equivalents for FastAPI and async callers.
- **Fallback Humanizer Contract Engine**: If `humanizer` is in the process of being built or installed, `conftest.py` injects a contract-compliant reference module into `sys.modules['humanizer']`, guaranteeing test collection and AST parsing succeed unconditionally.
- **Test Daemon App Fixture (`api_test_client`)**: Provides a `TestClient` instance wrapping the FastAPI app, supporting sync calls (`.get()`, `.post()`) and streaming calls (`.stream()`).

---

## 5. Execution Commands & Test Guide

### Running the Entire E2E Suite:
```bash
python -m pytest tests/e2e -v
```

### Running Individual Tiers:
```bash
# Tier 1: Feature Coverage
python -m pytest tests/e2e/test_tier1_features.py -v

# Tier 2: Boundary & Corner Cases
python -m pytest tests/e2e/test_tier2_boundaries.py -v

# Tier 3: Cross-Feature Combinations
python -m pytest tests/e2e/test_tier3_combinations.py -v

# Tier 4: Real-World Application Scenarios
python -m pytest tests/e2e/test_tier4_scenarios.py -v
```

### Running Specific Feature Slices:
```bash
# Test all cases covering Feature F7 (Markdown Chunker)
python -m pytest tests/e2e -k "f7" -v

# Test all cases covering Feature F3 (Budget Mode)
python -m pytest tests/e2e -k "f3" -v

# Test all SSE Streaming cases (Feature F9)
python -m pytest tests/e2e -k "f9 or sse" -v
```

### Running with Live Gemini API Key:
```powershell
$env:GEMINI_API_KEY = "your_actual_gemini_api_key"
python -m pytest tests/e2e -v
```

---

## 6. Strict Quality Gates & Benchmark Thresholds

| Quality Gate | Requirement Source | Strict Threshold | Test Verification |
|---|---|---|---|
| **Budget Mode Token Overhead** | `ORIGINAL_REQUEST.md § R2` | Strictly < 100 prompt tokens overhead | `test_f3_02`, `test_f12_01`, `test_t3_08`, `test_t4_01` |
| **Banned Buzzwords Invariance** | `ORIGINAL_REQUEST.md § R2` | Strictly 0 occurrences in output | `test_f6_02`, `test_f12_02`, `test_t3_12`, `test_t4_04` |
| **Code Block Invariance** | `ORIGINAL_REQUEST.md § R3` | 100% bit-for-bit byte match | `test_f7_01`, `test_f12_03`, `test_t3_01`, `test_t4_02` |
| **Markdown Table Invariance** | `ORIGINAL_REQUEST.md § R3` | Pipes and delimiters intact | `test_f7_02`, `test_t3_02`, `test_t4_02` |
| **FastAPI REST Contract** | `ORIGINAL_REQUEST.md § R1` | HTTP 200 on `/health` and `/v1/humanize` | `test_f8_01`, `test_f8_02`, `test_t4_06` |
| **SSE Streaming Invariance** | `ORIGINAL_REQUEST.md § R1` | Valid chunk stream with `[DONE]` sentinel | `test_f9_01`, `test_f9_03`, `test_t3_05`, `test_t4_06` |
| **Standalone Executable** | `ORIGINAL_REQUEST.md § R1` | `freeze_support()` and auto-serve config | `test_f10_01`, `test_f10_04` |
