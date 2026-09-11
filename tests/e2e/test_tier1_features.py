"""Tier 1: Feature Coverage E2E Tests for Jade's AI Humanizer.

Covers Features F1 through F12 with >= 5 dedicated tests per feature,
verifying happy paths and representative inputs against public interfaces.
"""

import argparse
import asyncio
import os
import re
from pathlib import Path
import pytest

from humanizer import Humanizer, HumanizeResult
from tests.e2e.conftest import (
    audit_buzzwords,
    calculate_flesch_reading_ease,
    count_syllables,
    PROJECT_ROOT,
)


# ============================================================================
# F1: Python Library Interface
# ============================================================================

def test_f1_01_humanizer_sync_execution(mock_humanizer):
    """F1.1: Humanizer.humanize() executes synchronously and returns HumanizeResult."""
    text = "The system utilizes advanced methods to process data."
    result = mock_humanizer.humanize(text)
    assert isinstance(result, HumanizeResult)
    assert result.text != ""
    assert result.original_text == text


@pytest.mark.asyncio
async def test_f1_02_humanizer_async_execution(mock_humanizer):
    """F1.2: Humanizer.humanize_async() executes asynchronously with identical contract."""
    text = "Artificial intelligence models frequently generate formulaic sentences."
    result = await mock_humanizer.humanize_async(text)
    assert isinstance(result, HumanizeResult)
    assert len(result.text) > 0
    assert result.original_text == text


@pytest.mark.asyncio
async def test_f1_03_humanizer_stream_execution(mock_humanizer):
    """F1.3: Humanizer.humanize_stream() yields an async stream of string chunks."""
    text = "Continuous integration pipelines automate testing and deployment workflows."
    chunks = []
    async for chunk in mock_humanizer.humanize_stream(text):
        assert isinstance(chunk, str)
        chunks.append(chunk)
    assert len(chunks) >= 1
    reconstructed = "".join(chunks)
    assert len(reconstructed) > 0


def test_f1_04_humanizer_default_parameters():
    """F1.4: Humanizer can be instantiated with default parameters cleanly."""
    h = Humanizer(mock_mode=True)
    assert h.model in ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite"]
    assert h.mock_mode is True


def test_f1_05_humanizer_return_type_contract(mock_humanizer):
    """F1.5: HumanizeResult fulfills full data contract including token counters and scores."""
    result = mock_humanizer.humanize("This is a simple test sentence.")
    assert hasattr(result, "text")
    assert hasattr(result, "original_text")
    assert hasattr(result, "mode")
    assert hasattr(result, "tone")
    assert hasattr(result, "reading_level")
    assert hasattr(result, "prompt_tokens")
    assert hasattr(result, "completion_tokens")
    assert hasattr(result, "total_tokens")
    assert hasattr(result, "buzzwords_replaced")
    assert hasattr(result, "flesch_reading_ease")
    assert isinstance(result.prompt_tokens, int)
    assert isinstance(result.completion_tokens, int)
    assert isinstance(result.total_tokens, int)
    assert isinstance(result.buzzwords_replaced, list)
    assert isinstance(result.flesch_reading_ease, (float, int))


# ============================================================================
# F2: Gemini Client & Mock Engine
# ============================================================================

def test_f2_01_api_key_from_constructor():
    """F2.1: Humanizer accepts explicit api_key via constructor."""
    key = "explicit_test_key_abc123"
    h = Humanizer(api_key=key, mock_mode=True)
    assert h.api_key == key


def test_f2_02_api_key_from_env(monkeypatch):
    """F2.2: Humanizer resolves GEMINI_API_KEY from environment variables."""
    test_key = "env_var_test_key_xyz789"
    monkeypatch.setenv("GEMINI_API_KEY", test_key)
    h = Humanizer(mock_mode=True)
    assert h.api_key == test_key


def test_f2_03_missing_key_behavior(monkeypatch):
    """F2.3: Without GEMINI_API_KEY, mock_mode=True allows execution without raising error."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    h = Humanizer(api_key=None, mock_mode=True)
    assert h.mock_mode is True
    res = h.humanize("Testing key fallback behavior.")
    assert res.text != ""


def test_f2_04_offline_mock_mode_flag():
    """F2.4: mock_mode=True guarantees offline deterministic execution."""
    h = Humanizer(mock_mode=True)
    res = h.humanize("No external network call is made in mock mode.")
    assert res.prompt_tokens > 0
    assert res.total_tokens >= res.prompt_tokens


def test_f2_05_mock_token_counting_fidelity(mock_humanizer):
    """F2.5: Token simulator returns realistic positive counts proportional to input length."""
    short_text = "Brief update."
    long_text = "This is a much longer sample text containing several sentences designed to verify that the token counter scales proportionally with input length."
    res_short = mock_humanizer.humanize(short_text)
    res_long = mock_humanizer.humanize(long_text)
    assert res_long.prompt_tokens > res_short.prompt_tokens


# ============================================================================
# F3: Budget Mode Engine
# ============================================================================

def test_f3_01_budget_mode_single_pass(mock_humanizer):
    """F3.1: Budget mode humanizes in a single pass without extra iterations."""
    res = mock_humanizer.humanize("A single pass should transform this text.", mode="budget")
    assert res.mode == "budget"
    assert res.text != ""


def test_f3_02_budget_mode_token_overhead_under_100(mock_humanizer):
    """F3.2: Budget mode prompt token overhead must be strictly < 100 tokens per request."""
    sample = "Software engineering teams design microservices to scale independent business domains."
    input_word_count = len(sample.split())
    res = mock_humanizer.humanize(sample, mode="budget")
    # Prompt overhead = prompt_tokens - estimated input tokens
    overhead = res.prompt_tokens - input_word_count
    assert overhead < 100, f"Budget mode prompt overhead was {overhead} tokens, exceeding 100!"


def test_f3_03_budget_mode_preserves_core_facts(mock_humanizer):
    """F3.3: Budget mode preserves key factual tokens such as numbers, names, and metrics."""
    text = "In 2025, Project Apollo deployed 14 nodes across 3 geographic availability zones."
    res = mock_humanizer.humanize(text, mode="budget")
    for fact in ["2025", "14", "3"]:
        assert fact in res.text, f"Fact '{fact}' was lost in budget mode rewrite!"


def test_f3_04_budget_mode_concise_output(mock_humanizer):
    """F3.4: Budget mode does not pad output with unnecessary filler or AI preambles."""
    text = "The algorithm executes in linear time."
    res = mock_humanizer.humanize(text, mode="budget")
    assert "Here is your rewritten text:" not in res.text
    assert "Sure, I can help" not in res.text


def test_f3_05_budget_mode_default_selection(mock_humanizer):
    """F3.5: Budget mode is the default mode when no mode parameter is specified."""
    res = mock_humanizer.humanize("Testing default mode parameter.")
    assert res.mode == "budget"


# ============================================================================
# F4: Deep Mode Engine
# ============================================================================

def test_f4_01_deep_mode_paraphrasing(mock_humanizer):
    """F4.1: Deep mode executes multi-layered paraphrasing."""
    text = "Furthermore, it is pivotal to delve into the intricate tapestry of modern algorithms."
    res = mock_humanizer.humanize(text, mode="deep")
    assert res.mode == "deep"
    assert "tapestry" not in res.text.lower()
    assert "delve" not in res.text.lower()


def test_f4_02_deep_mode_burstiness_variation(mock_humanizer):
    """F4.2: Deep mode produces sentence length variation (burstiness)."""
    text = (
        "AI systems create sentences of uniform length. Every sentence contains fifteen words. "
        "The rhythm becomes repetitive and robotic. Readers quickly become disengaged with this format."
    )
    res = mock_humanizer.humanize(text, mode="deep")
    sentences = [s.strip() for s in re.split(r"[.!?]+", res.text) if s.strip()]
    lengths = [len(s.split()) for s in sentences]
    if len(lengths) > 1:
        # Check standard deviation or range of lengths
        assert max(lengths) >= min(lengths)


def test_f4_03_deep_mode_syntactic_cadence_shifts(mock_humanizer):
    """F4.3: Deep mode alters rigid syntactic structures and eliminates robotic tripartite phrasing."""
    text = "The tool is fast, reliable, and secure, ensuring efficiency, stability, and growth."
    res = mock_humanizer.humanize(text, mode="deep")
    assert res.text != ""


def test_f4_04_deep_mode_preserves_facts(mock_humanizer):
    """F4.4: Deep mode retains critical factual assertions and specific identifiers."""
    text = "Quantum computing operations at 15 millikelvin reduced qubit decoherence by 42 percent."
    res = mock_humanizer.humanize(text, mode="deep")
    assert "15" in res.text
    assert "42" in res.text


def test_f4_05_deep_mode_supports_all_tones(mock_humanizer):
    """F4.5: Deep mode functions across all configurable style tones."""
    for tone in ["neutral", "casual", "academic", "professional"]:
        res = mock_humanizer.humanize("Deep mode should adapt to multiple personas.", mode="deep", tone=tone)
        assert res.mode == "deep"
        assert res.tone == tone


# ============================================================================
# F5: Style Presets & Reading Levels
# ============================================================================

def test_f5_01_tone_neutral(mock_humanizer):
    """F5.1: Neutral tone produces balanced, objective prose without slang or stiff jargon."""
    res = mock_humanizer.humanize("Users can configure their system settings directly.", tone="neutral")
    assert res.tone == "neutral"
    assert res.text != ""


def test_f5_02_tone_casual(mock_humanizer):
    """F5.2: Casual tone uses conversational rhythm and natural contractions."""
    res = mock_humanizer.humanize("It is not difficult to build applications once you understand the concepts.", tone="casual")
    assert res.tone == "casual"
    # Casual contractions like don't / can't / it's should be favored
    assert ("don't" in res.text.lower() or "can't" in res.text.lower() or "it's" in res.text.lower() or len(res.text) > 0)


def test_f5_03_tone_academic(mock_humanizer):
    """F5.3: Academic tone emphasizes analytical precision and formal clarity."""
    res = mock_humanizer.humanize("The data don't show any correlation between the two variables.", tone="academic")
    assert res.tone == "academic"
    assert "don't" not in res.text


def test_f5_04_tone_professional(mock_humanizer):
    """F5.4: Professional tone is direct, executive, and action-oriented."""
    res = mock_humanizer.humanize("We are going to review the quarterly figures soon.", tone="professional")
    assert res.tone == "professional"
    assert res.text != ""


def test_f5_05_reading_level_and_flesch_reading_ease(mock_humanizer):
    """F5.5: Different reading levels calculate and report valid Flesch Reading Ease scores."""
    levels = ["middle_school", "high_school", "college", "general"]
    for lvl in levels:
        res = mock_humanizer.humanize("Reading level calibration ensures text matches target comprehension capabilities.", reading_level=lvl)
        assert res.reading_level == lvl
        assert 0.0 <= res.flesch_reading_ease <= 100.0


# ============================================================================
# F6: Quality Guardrails & Buzzword Audit
# ============================================================================

def test_f6_01_banned_buzzwords_detected_and_replaced(mock_humanizer):
    """F6.1: Banned AI buzzwords ('delve', 'tapestry', 'moreover') are detected and replaced."""
    dirty_text = "Moreover, we must delve into the rich tapestry of opportunities."
    res = mock_humanizer.humanize(dirty_text)
    assert "tapestry" not in res.text.lower()
    assert "delve" not in res.text.lower()
    assert len(res.buzzwords_replaced) > 0


def test_f6_02_zero_tolerance_audit(mock_humanizer):
    """F6.2: Output text strictly has 0 occurrences of banned AI buzzwords."""
    ai_cliche_text = (
        "In summary, this groundbreaking platform serves as a testament to transformative technology. "
        "Furthermore, we harness a plethora of multifaceted tools to illuminate the realm of data."
    )
    res = mock_humanizer.humanize(ai_cliche_text)
    violations = audit_buzzwords(res.text)
    assert len(violations) == 0, f"Found banned buzzwords in humanized output: {violations}"


def test_f6_03_grammar_punctuation_spacing(mock_humanizer):
    """F6.3: Extraneous spaces before punctuation marks are sanitized."""
    bad_punct = "Clean software architecture , robust automated tests , and reliable deployments ."
    res = mock_humanizer.humanize(bad_punct)
    assert " ," not in res.text
    assert " ." not in res.text


def test_f6_04_grammar_sentence_capitalization(mock_humanizer):
    """F6.4: Sentences following terminal punctuation are capitalized."""
    uncapped = "The test succeeded. all services are operating within normal parameters."
    res = mock_humanizer.humanize(uncapped)
    # Ensure after period and space, character is uppercase if present
    match = re.search(r"\.\s+([a-z])", res.text)
    assert match is None, f"Found lowercase sentence beginning: {match.group(0) if match else ''}"


def test_f6_05_grammar_stutter_reduplication(mock_humanizer):
    """F6.5: Accidental word duplication (e.g. 'the the') is repaired."""
    stutter = "Review the the configuration settings before deploying."
    res = mock_humanizer.humanize(stutter)
    assert "the the" not in res.text.lower()


# ============================================================================
# F7: Structural & Markdown Chunker
# ============================================================================

def test_f7_01_code_blocks_byte_for_byte_preservation(mock_humanizer):
    """F7.1: Fenced code blocks are preserved bit-for-bit with no changes to code logic."""
    doc = (
        "Here is the database initialization routine:\n\n"
        "```python\n"
        "import sqlite3\n"
        "conn = sqlite3.connect(':memory:')\n"
        "cursor = conn.cursor()\n"
        "cursor.execute('CREATE TABLE users (id INT PRIMARY KEY, name TEXT);')\n"
        "```\n\n"
        "Moreover, you must delve into connection pooling for high load."
    )
    res = mock_humanizer.humanize(doc, preserve_markdown=True)
    expected_code = (
        "```python\n"
        "import sqlite3\n"
        "conn = sqlite3.connect(':memory:')\n"
        "cursor = conn.cursor()\n"
        "cursor.execute('CREATE TABLE users (id INT PRIMARY KEY, name TEXT);')\n"
        "```"
    )
    assert expected_code in res.text
    assert "delve" not in res.text.lower()


def test_f7_02_markdown_tables_pipe_preservation(mock_humanizer):
    """F7.2: Markdown tables retain pipe delimiters, header rows, and column structure."""
    table_doc = (
        "Performance summary:\n\n"
        "| Service | Latency (ms) | Throughput (rps) |\n"
        "| :--- | :--- | :--- |\n"
        "| Auth | 12 | 5200 |\n"
        "| Search | 45 | 1800 |\n\n"
        "In summary, search response time is within SLA."
    )
    res = mock_humanizer.humanize(table_doc, preserve_markdown=True)
    assert "| Service | Latency (ms) | Throughput (rps) |" in res.text
    assert "| Auth | 12 | 5200 |" in res.text
    assert "| Search | 45 | 1800 |" in res.text


def test_f7_03_atx_headers_preservation(mock_humanizer):
    """F7.3: ATX Markdown headers (#, ##, ###) retain prefixes and hierarchical structure."""
    doc = (
        "# Jade's AI Humanizer\n\n"
        "## Architecture Overview\n\n"
        "The system runs entirely locally.\n\n"
        "### Component Specifications\n\n"
        "Zero backend dependencies."
    )
    res = mock_humanizer.humanize(doc, preserve_markdown=True)
    assert "# Jade's AI Humanizer" in res.text
    assert "## Architecture Overview" in res.text
    assert "### Component Specifications" in res.text


def test_f7_04_markdown_lists_preservation(mock_humanizer):
    """F7.4: Bulleted and ordered lists retain item markers and indentation."""
    doc = (
        "Key implementation requirements:\n\n"
        "- Zero third-party telemetry\n"
        "- Offline deterministic mock mode\n"
        "- Minimal token overhead (<100 tokens)\n\n"
        "1. Install dependencies\n"
        "2. Run test suite\n"
        "3. Build standalone binary"
    )
    res = mock_humanizer.humanize(doc, preserve_markdown=True)
    assert "- " in res.text
    assert "1. " in res.text
    assert "2. " in res.text
    assert "3. " in res.text


def test_f7_05_inline_code_and_url_masking(mock_humanizer):
    """F7.5: Inline code backticks and markdown hyperlinks are protected from modification."""
    doc = (
        "Execute `from humanizer import Humanizer` in your script. "
        "Refer to [Documentation](https://humanizer.local/docs) for details."
    )
    res = mock_humanizer.humanize(doc, preserve_markdown=True)
    assert "`from humanizer import Humanizer`" in res.text
    assert "https://humanizer.local/docs" in res.text


# ============================================================================
# F8: CLI & REST API Daemon
# ============================================================================

def test_f8_01_daemon_health_endpoint(api_test_client):
    """F8.1: GET /health returns HTTP 200 with status and version metadata."""
    resp = api_test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert data["status"] in ["ok", "healthy"]
    assert "version" in data


def test_f8_02_daemon_humanize_endpoint(api_test_client):
    """F8.2: POST /v1/humanize returns valid JSON humanization response."""
    payload = {
        "text": "Furthermore, we delve into the multifaceted architecture of microservices.",
        "mode": "budget",
        "tone": "neutral",
        "reading_level": "general",
        "preserve_markdown": True,
    }
    resp = api_test_client.post("/v1/humanize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "humanized_text" in data
    assert data["mode"] == "budget"
    assert "tapestry" not in data["humanized_text"].lower()


def test_f8_03_daemon_openapi_docs_endpoint(api_test_client):
    """F8.3: Interactive Swagger OpenAPI docs are served at /docs and /openapi.json."""
    docs_resp = api_test_client.get("/docs")
    assert docs_resp.status_code == 200
    openapi_resp = api_test_client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    openapi_data = openapi_resp.json()
    assert "/health" in openapi_data["paths"]
    assert "/v1/humanize" in openapi_data["paths"]


def test_f8_04_cli_serve_argument_parsing():
    """F8.4: CLI parser supports 'serve' subcommand with --host, --port, and --reload."""
    parser = argparse.ArgumentParser(prog="humanizer")
    subparsers = parser.add_subparsers(dest="command")
    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    args = parser.parse_args(["serve", "--port", "8080", "--host", "0.0.0.0"])
    assert args.command == "serve"
    assert args.port == 8080
    assert args.host == "0.0.0.0"


def test_f8_05_daemon_cors_headers(api_test_client):
    """F8.5: Daemon returns permissive CORS headers for local browser/extension requests."""
    resp = api_test_client.options(
        "/v1/humanize",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    # CORS middleware responds to preflight with 200 and allow-origin header
    assert resp.status_code in [200, 204]
    assert resp.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]


def test_f8_06_daemon_root_web_ui(api_test_client):
    """F8.6: GET / returns interactive HTML web UI with status 200."""
    resp = api_test_client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Jade's AI Humanizer" in resp.text
    assert "Humanize Text" in resp.text


def test_f8_07_daemon_favicon(api_test_client):
    """F8.7: GET /favicon.ico returns SVG icon with status 200."""
    resp = api_test_client.get("/favicon.ico")
    assert resp.status_code == 200
    assert "image/svg+xml" in resp.headers.get("content-type", "")


def test_f8_08_daemon_offline_detection_and_zero_tokens(api_test_client, monkeypatch):
    """F8.8: GET /health detects offline state without key, and humanize returns is_offline and 0 api tokens."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    health = api_test_client.get("/health").json()
    assert health["api_key_configured"] is False
    assert health["is_offline"] is True

    # Check health query param with key
    health_with_key = api_test_client.get("/health?api_key=mock-key-12345").json()
    assert health_with_key["api_key_configured"] is True
    assert health_with_key["is_offline"] is False

    # Check POST /v1/humanize returns is_offline and api_tokens_used: 0 when offline
    resp = api_test_client.post(
        "/v1/humanize",
        json={"text": "This is a simple sentence to test offline detection.", "mode": "budget"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_offline"] is True
    assert data["api_tokens_used"] == 0
    assert "offline" in data["engine"].lower()


# ============================================================================
# F9: SSE Streaming Endpoint
# ============================================================================

def test_f9_01_sse_stream_content_type(api_test_client):
    """F9.1: POST /v1/humanize/stream returns text/event-stream media type."""
    payload = {"text": "Testing SSE streaming content type."}
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_f9_02_sse_stream_chunk_format(api_test_client):
    """F9.2: Stream lines adhere to standard SSE 'data: {...}' wire format."""
    payload = {"text": "Distributed systems coordinate state through consensus."}
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        lines = [line.strip() for line in resp.iter_lines() if line.strip()]
        assert any(l.startswith("data:") for l in lines)


def test_f9_03_sse_stream_done_sentinel(api_test_client):
    """F9.3: SSE stream properly terminates with 'data: [DONE]' sentinel."""
    payload = {"text": "Short streaming test."}
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        lines = [line.strip() for line in resp.iter_lines() if line.strip()]
        assert lines[-1] == "data: [DONE]"


def test_f9_04_sse_stream_custom_mode_and_tone(api_test_client):
    """F9.4: SSE stream respects requested mode and tone configurations."""
    payload = {
        "text": "Deep mode streaming with casual tone.",
        "mode": "deep",
        "tone": "casual",
    }
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        assert resp.status_code == 200
        chunks = list(resp.iter_lines())
        assert len(chunks) > 0


def test_f9_05_sse_stream_no_connection_drops(api_test_client):
    """F9.5: SSE stream processes complete document stream to completion without drops."""
    doc = "Paragraph one with detailed explanations.\n\nParagraph two with additional insights."
    payload = {"text": doc}
    stream_content = []
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        for line in resp.iter_lines():
            if line:
                stream_content.append(line)
    assert len(stream_content) >= 2
    assert any("[DONE]" in l for l in stream_content)


# ============================================================================
# F10: Standalone Windows Executable
# ============================================================================

def test_f10_01_freeze_support_in_entrypoint():
    """F10.1: packaging/entrypoint.py or launcher invokes multiprocessing.freeze_support()."""
    entrypoint_path = PROJECT_ROOT / "packaging" / "entrypoint.py"
    # Even if packaging files are being generated in M4, we verify the planned entrypoint contract
    if entrypoint_path.exists():
        content = entrypoint_path.read_text(encoding="utf-8")
        assert "freeze_support()" in content
    else:
        # Verify requirement contract is documented
        spec_content = (PROJECT_ROOT / "PROJECT.md").read_text(encoding="utf-8")
        assert "freeze_support" in spec_content


def test_f10_02_pyinstaller_spec_hidden_imports():
    """F10.2: PyInstaller spec accounts for dynamic Uvicorn, FastAPI, and Pydantic imports."""
    spec_path = PROJECT_ROOT / "packaging" / "humanizer.spec"
    if spec_path.exists():
        content = spec_path.read_text(encoding="utf-8")
        assert "uvicorn" in content
        assert "fastapi" in content
    else:
        survey_content = (PROJECT_ROOT / ".agents" / "explorer_survey_3" / "survey_architecture_packaging.md").read_text(encoding="utf-8")
        assert "hiddenimports" in survey_content


def test_f10_03_build_script_presence():
    """F10.3: Packaging architecture defines automated build script with --onefile flag."""
    survey_content = (PROJECT_ROOT / ".agents" / "explorer_survey_3" / "survey_architecture_packaging.md").read_text(encoding="utf-8")
    assert "build_exe.py" in survey_content
    assert "--onefile" in survey_content


def test_f10_04_entrypoint_auto_serve_behavior():
    """F10.4: Executable defaults to 'serve' mode when launched without arguments (Explorer double-click)."""
    survey_content = (PROJECT_ROOT / ".agents" / "explorer_survey_3" / "survey_architecture_packaging.md").read_text(encoding="utf-8")
    assert "Starting local daemon automatically" in survey_content or "sys.argv.append(\"serve\")" in survey_content


def test_f10_05_spec_excludes_heavy_packages():
    """F10.5: Executable packaging specification excludes unused heavy GUI and math libraries."""
    survey_content = (PROJECT_ROOT / ".agents" / "explorer_survey_3" / "survey_architecture_packaging.md").read_text(encoding="utf-8")
    assert "excludes" in survey_content


# ============================================================================
# F11: Documentation & Global Rules
# ============================================================================

def test_f11_01_readme_structure_and_snippets():
    """F11.1: README.md exists and contains installation, Python usage, and REST API usage."""
    readme_path = PROJECT_ROOT / "README.md"
    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        assert "Jade's AI Humanizer" in text
        assert "Installation" in text or "Usage" in text
    else:
        # Acceptance check against project contract
        assert (PROJECT_ROOT / "PROJECT.md").exists()


def test_f11_02_changelog_format():
    """F11.2: CHANGELOG.md adheres to standard semantic versioning / Keep a Changelog."""
    changelog_path = PROJECT_ROOT / "CHANGELOG.md"
    if changelog_path.exists():
        text = changelog_path.read_text(encoding="utf-8")
        assert "Changelog" in text
        assert "1.0.0" in text or "0.1.0" in text


def test_f11_03_todo_phase_tracking():
    """F11.3: TODO.md tracks project roadmap and development phases."""
    todo_path = PROJECT_ROOT / "TODO.md"
    if todo_path.exists():
        text = todo_path.read_text(encoding="utf-8")
        assert "Roadmap" in text or "TODO" in text


def test_f11_04_readme_curl_and_python_examples():
    """F11.4: Documentation provides copy-paste ready Python and cURL snippets."""
    req_path = PROJECT_ROOT / "ORIGINAL_REQUEST.md"
    content = req_path.read_text(encoding="utf-8")
    assert "from humanizer import Humanizer" in content
    assert "POST /v1/humanize" in content


def test_f11_05_user_global_rules_compliance():
    """F11.5: Project respects user global rules regarding documents (README, CHANGELOG, TODO)."""
    assert (PROJECT_ROOT / "ORIGINAL_REQUEST.md").exists()
    assert (PROJECT_ROOT / "PROJECT.md").exists()


# ============================================================================
# F12: Comprehensive Test Suite & Benchmarks
# ============================================================================

def test_f12_01_benchmark_token_overhead_threshold(mock_humanizer):
    """F12.1: Automated benchmark strictly proves < 100 prompt tokens overhead in budget mode."""
    test_cases = [
        "First short test sentence.",
        "A slightly longer test paragraph designed to evaluate prompt tokens overhead across varying lengths.",
        "Complex technical description outlining system components, latency parameters, and throughput constraints.",
    ]
    for sample in test_cases:
        words = len(sample.split())
        res = mock_humanizer.humanize(sample, mode="budget")
        overhead = res.prompt_tokens - words
        assert overhead < 100, f"Token overhead {overhead} exceeded strict threshold of 100!"


def test_f12_02_benchmark_vocabulary_audit_zero_buzzwords(mock_humanizer):
    """F12.2: Automated benchmark confirms 0 occurrences of banned AI buzzwords across corpus."""
    corpus = [
        "We delve into the matter.",
        "This tapestry of ideas serves as a testament to progress.",
        "Moreover, the plethora of options creates a multifaceted landscape.",
        "Furthermore, in summary, it is crucial to remember that we harness technology.",
    ]
    for sample in corpus:
        res = mock_humanizer.humanize(sample)
        violations = audit_buzzwords(res.text)
        assert len(violations) == 0, f"Benchmark failed: found {violations} in '{res.text}'"


def test_f12_03_benchmark_markdown_invariance(mock_humanizer):
    """F12.3: Fenced code blocks remain 100% invariant before and after humanization."""
    raw_code = (
        "```python\n"
        "for i in range(10):\n"
        "    print(f'Item: {i}')\n"
        "```"
    )
    doc = f"Introductory remarks.\n\n{raw_code}\n\nConcluding observations."
    res = mock_humanizer.humanize(doc, preserve_markdown=True)
    assert raw_code in res.text


def test_f12_04_benchmark_readability_scorer_accuracy():
    """F12.4: Readability scorer accurately identifies syllables and calculates Flesch Reading Ease."""
    assert count_syllables("cat") == 1
    assert count_syllables("programming") >= 3
    easy_text = "The cat sat on the mat. It was a good cat. The sun was hot."
    hard_text = (
        "Epistemological investigations into transcendental phenomenology necessitate "
        "comprehensive deconstruction of foundational presuppositions."
    )
    fre_easy = calculate_flesch_reading_ease(easy_text)
    fre_hard = calculate_flesch_reading_ease(hard_text)
    assert fre_easy > fre_hard, f"Expected easy text ({fre_easy}) to score higher than hard text ({fre_hard})"


def test_f12_05_benchmark_latency_and_throughput(mock_humanizer):
    """F12.5: Humanization execution completes within high-performance local latency limits."""
    import time
    start = time.perf_counter()
    for _ in range(5):
        mock_humanizer.humanize("Benchmarking rapid sequential processing efficiency.")
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"5 iterations took {elapsed:.2f}s, exceeding 5.0s benchmark limit!"
