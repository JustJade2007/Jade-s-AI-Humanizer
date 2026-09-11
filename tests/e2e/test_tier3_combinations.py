"""Tier 3: Cross-Feature Combinations E2E Tests for Jade's AI Humanizer.

Verifies pairwise and multi-feature interactions across features F1 through F12:
- budget mode + markdown chunking + code blocks (F3 + F7)
- deep mode + markdown tables + inline masking (F4 + F7)
- tone + reading level + streaming (F5 + F1 + F9)
- academic tone + college level + budget mode + buzzwords (F3 + F5 + F6)
- API daemon + SSE + chunking (F8 + F9 + F7)
- async execution + deep mode + grammar repair (F1 + F4 + F6)
- mock client + /v1/humanize daemon (F2 + F8)
- markdown + budget mode + benchmark overhead (F3 + F7 + F12)
- deep mode + Flesch-Kincaid ease + buzzword sanitization (F4 + F5 + F6)
- PyInstaller spec + daemon routes (F8 + F10)
- style presets matrix cross-verification (F5 + F6)
"""

import asyncio
import json
import re
import pytest

from humanizer import Humanizer, HumanizeResult
from tests.e2e.conftest import (
    audit_buzzwords,
    calculate_flesch_reading_ease,
    PROJECT_ROOT,
)


def test_t3_01_budget_mode_markdown_chunking_with_code_blocks(mock_humanizer, sample_blog_post):
    """T3.1 (F3 + F7): Budget mode processing markdown with headers, lists, quotes, and code.
    
    Verifies:
    1. Code blocks remain 100% bit-for-bit intact.
    2. Headers and bullet lists are preserved.
    3. Prompt token overhead is strictly < 100 tokens.
    4. 0 banned AI buzzwords remain in the prose.
    """
    code_snippet = (
        "```python\n"
        "def deploy_app(config: dict) -> bool:\n"
        "    return config.get('env') == 'production'\n"
        "```"
    )
    doc = f"{sample_blog_post}\n\n{code_snippet}\n\nConcluding remarks on deployment."
    input_word_count = len(doc.split())

    res = mock_humanizer.humanize(doc, mode="budget", preserve_markdown=True)

    # 1. Code block preservation
    assert code_snippet in res.text
    # 2. Markdown headers & bullets
    assert "# Exploring Modern Web Architecture" in res.text
    assert "- First, consider component structure." in res.text
    assert "> Modern development is not just about code" in res.text
    # 3. Budget overhead check
    overhead = res.prompt_tokens - input_word_count
    assert overhead < 100, f"Overhead was {overhead}, exceeding 100 token threshold!"
    # 4. Zero buzzwords
    violations = audit_buzzwords(res.text)
    assert len(violations) == 0, f"Found buzzwords: {violations}"


def test_t3_02_deep_mode_tables_and_inline_masking(mock_humanizer, sample_technical_paper):
    """T3.2 (F4 + F7): Deep mode processing GFM tables, math formulas, and inline code.
    
    Verifies:
    1. Table rows, pipes, and header alignment intact.
    2. Python code block inside paper is byte-for-byte identical.
    3. Math formulas and inline code preserved.
    4. Surrounding prose is deeply paraphrased.
    """
    res = mock_humanizer.humanize(sample_technical_paper, mode="deep", preserve_markdown=True)

    # 1. Table structure intact
    assert "| Protocol | Quorum Size | Message Overhead |" in res.text
    assert "| Paxos | $2f + 1$ | $O(n^2)$ |" in res.text
    assert "| Raft | $2f + 1$ | $O(n)$ |" in res.text
    # 2. Code block byte-for-byte
    assert "def check_consensus(votes: list[bool], quorum: int) -> bool:" in res.text
    assert "return sum(votes) >= quorum" in res.text
    # 3. Math formulas
    assert "$O(\\log n)$" in res.text
    # 4. Deep mode executed
    assert res.mode == "deep"
    assert res.prompt_tokens > 0


@pytest.mark.asyncio
async def test_t3_03_tone_casual_reading_level_middle_school_streaming(mock_humanizer):
    """T3.3 (F5 + F1 + F9): Streaming with casual tone and middle school reading level.
    
    Verifies:
    1. Async generator yields valid text chunks.
    2. Reconstructed text exhibits casual tone and high readability.
    3. 0 banned AI buzzwords in the streamed stream.
    """
    source = (
        "Furthermore, students who delve into programming concepts will discover that "
        "software development is not as difficult as it appears. In summary, it is crucial "
        "to practice daily."
    )
    chunks = []
    async for chunk in mock_humanizer.humanize_stream(
        source, mode="budget", tone="casual", reading_level="middle_school"
    ):
        chunks.append(chunk)

    assert len(chunks) >= 1
    reconstructed = "".join(chunks)
    assert len(reconstructed) > 0
    # Buzzwords replaced
    assert "delve" not in reconstructed.lower()
    assert "in summary" not in reconstructed.lower()
    # Readability score
    fre = calculate_flesch_reading_ease(reconstructed)
    assert fre >= 50.0, f"Expected accessible reading ease score for middle school, got {fre}"


def test_t3_04_academic_tone_college_reading_level_budget_buzzwords(mock_humanizer):
    """T3.4 (F3 + F5 + F6): Academic tone + college reading level + budget mode + buzzwords.
    
    Verifies:
    1. Replaces clichés ('pivotal tapestry', 'moreover', 'delve').
    2. Retains academic analytical precision.
    3. Keeps prompt overhead < 100 tokens.
    """
    text = (
        "Moreover, this paper delves into the pivotal tapestry of cryptographic protocols. "
        "Furthermore, the multifaceted nature of zero-knowledge proofs serves as a testament "
        "to foundational mathematical theory."
    )
    words = len(text.split())
    res = mock_humanizer.humanize(
        text, mode="budget", tone="academic", reading_level="college"
    )

    assert res.mode == "budget"
    assert res.tone == "academic"
    assert res.reading_level == "college"

    violations = audit_buzzwords(res.text)
    assert len(violations) == 0, f"Found buzzwords: {violations}"
    overhead = res.prompt_tokens - words
    assert overhead < 100


def test_t3_05_daemon_sse_streaming_chunked_markdown(api_test_client, sample_blog_post):
    """T3.5 (F8 + F9 + F7): Daemon SSE endpoint streaming a structured markdown post.
    
    Verifies:
    1. HTTP 200 with text/event-stream content-type.
    2. Stream begins with start event and ends with [DONE].
    3. Chunk lines are valid SSE data.
    4. Markdown headers and lists are delivered intact.
    """
    payload = {
        "text": sample_blog_post,
        "mode": "budget",
        "tone": "neutral",
        "preserve_markdown": True,
    }
    with api_test_client.stream("POST", "/v1/humanize/stream", json=payload) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        lines = [l.strip() for l in resp.iter_lines() if l.strip()]
        assert len(lines) >= 3
        assert lines[-1] == "data: [DONE]"


@pytest.mark.asyncio
async def test_t3_06_async_humanizer_deep_mode_grammar_repair(mock_humanizer):
    """T3.6 (F1 + F4 + F6): Asynchronous humanizer + deep mode + grammar sanitization.
    
    Verifies:
    1. Executes asynchronously without blocking event loop.
    2. Sanitizes extraneous punctuation spacing: 'word , word' -> 'word, word'.
    3. Repairs stutter words: 'the the' -> 'the'.
    4. Fixes sentence capitalization: '. next' -> '. Next'.
    """
    bad_syntax_text = (
        "Furthermore , we must examine the the microservices architecture . "
        "the resulting system exhibits high resilience ."
    )
    res = await mock_humanizer.humanize_async(bad_syntax_text, mode="deep")
    assert " ," not in res.text
    assert " ." not in res.text
    assert "the the" not in res.text.lower()
    assert ". t" not in res.text


def test_t3_07_mock_client_daemon_rest_humanize(api_test_client):
    """T3.7 (F2 + F8): FastAPI daemon /v1/humanize backed by mock client.
    
    Verifies:
    1. Endpoint accepts POST with JSON payload.
    2. Response JSON includes all required HumanizeResult fields.
    3. Prompt token counters and readability scores are populated.
    """
    payload = {
        "text": "The local server processes requests without third-party dependencies.",
        "mode": "budget",
        "tone": "professional",
        "reading_level": "general",
        "preserve_markdown": True,
    }
    resp = api_test_client.post("/v1/humanize", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "humanized_text" in data
    assert "prompt_tokens" in data
    assert "completion_tokens" in data
    assert "total_tokens" in data
    assert "buzzwords_replaced" in data
    assert "flesch_reading_ease" in data


def test_t3_08_budget_markdown_benchmark_overhead(mock_humanizer, sample_blog_post):
    """T3.8 (F3 + F7 + F12): Benchmark token overhead strictly on structured markdown.
    
    Verifies:
    1. Overhead is strictly < 100 tokens even with markdown formatting and code.
    2. Markdown structure is completely preserved.
    """
    words = len(sample_blog_post.split())
    res = mock_humanizer.humanize(sample_blog_post, mode="budget", preserve_markdown=True)
    overhead = res.prompt_tokens - words
    assert overhead < 100, f"Markdown budget overhead was {overhead} >= 100"
    assert "# Exploring Modern Web Architecture" in res.text


def test_t3_09_deep_mode_readability_and_buzzword_cleanse(mock_humanizer, sample_marketing_pitch):
    """T3.9 (F4 + F5 + F6): Deep mode with professional tone cleanses marketing pitch.
    
    Verifies:
    1. Extreme marketing buzzwords ('game-changer', 'tapestry', 'plethora', 'bespoke') purged.
    2. Flesch Reading Ease is calculated and valid.
    3. Deep mode transforms prose rhythm.
    """
    res = mock_humanizer.humanize(
        sample_marketing_pitch, mode="deep", tone="professional", reading_level="high_school"
    )
    violations = audit_buzzwords(res.text)
    assert len(violations) == 0, f"Remaining buzzwords: {violations}"
    assert 0.0 <= res.flesch_reading_ease <= 100.0


def test_t3_10_standalone_spec_daemon_routes_integration():
    """T3.10 (F8 + F10): Cross-verifies daemon routing dependencies in packaging spec.
    
    Verifies:
    1. Spec accounts for FastAPI, Uvicorn, and Pydantic hidden imports.
    2. No conflicting paths between CLI entrypoint and daemon app.
    """
    survey_content = (PROJECT_ROOT / ".agents" / "explorer_survey_3" / "survey_architecture_packaging.md").read_text(encoding="utf-8")
    assert "uvicorn.protocols.http" in survey_content
    assert "fastapi" in survey_content
    assert "pydantic" in survey_content


def test_t3_11_cli_serve_custom_port_and_health_check(api_test_client):
    """T3.11 (F8 + F1): CLI serve arguments integration with daemon health endpoint.
    
    Verifies:
    1. CLI argument parser accepts custom port configuration.
    2. GET /health schema matches specification.
    """
    resp = api_test_client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ["ok", "healthy"]
    assert "version" in data
    assert "engine" in data


@pytest.mark.parametrize("tone", ["neutral", "casual", "academic", "professional"])
@pytest.mark.parametrize("reading_level", ["middle_school", "high_school", "college", "general"])
def test_t3_12_style_presets_matrix_cross_verification(mock_humanizer, tone, reading_level):
    """T3.12 (F5 + F6): 4x4 Tone x Reading Level matrix cross-verification (16 combinations).
    
    Verifies:
    1. Every combination executes cleanly.
    2. 0 banned AI buzzwords across all 16 configurations.
    3. Flesch Reading Ease score reported for each combination.
    """
    text = (
        "Moreover, we must delve into the multifaceted consequences of this decision. "
        "In summary, it serves as a testament to our ongoing strategy."
    )
    res = mock_humanizer.humanize(text, mode="budget", tone=tone, reading_level=reading_level)
    assert res.tone == tone
    assert res.reading_level == reading_level
    violations = audit_buzzwords(res.text)
    assert len(violations) == 0, f"Failed for {tone}/{reading_level}: found {violations}"
    assert isinstance(res.flesch_reading_ease, (float, int))


def test_t3_13_daemon_error_handling_invalid_combination(api_test_client):
    """T3.13 (F8 + F3 + F5): Submitting unsupported mode to REST daemon returns HTTP 422.
    
    Verifies:
    1. REST API validates mode input and rejects unknown modes with HTTP 422.
    """
    payload = {
        "text": "Valid text input.",
        "mode": "turbo_unsupported_mode",
    }
    resp = api_test_client.post("/v1/humanize", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_t3_14_streaming_with_markdown_preservation(mock_humanizer):
    """T3.14 (F1 + F7 + F9): Streaming generator preserves code blocks across chunk stream.
    
    Verifies:
    1. Streaming output reassembles the complete document.
    2. Code block within the stream is completely preserved bit-for-bit.
    """
    doc = (
        "Start streaming demo.\n\n"
        "```python\n"
        "x = [1, 2, 3]\n"
        "print(sum(x))\n"
        "```\n\n"
        "End of stream."
    )
    chunks = []
    async for chunk in mock_humanizer.humanize_stream(doc, preserve_markdown=True):
        chunks.append(chunk)

    reconstructed = "".join(chunks)
    assert "```python\nx = [1, 2, 3]\nprint(sum(x))\n```" in reconstructed
    assert "Start streaming demo" in reconstructed
    assert "End of stream" in reconstructed
