"""Empirical Challenger Test Suite for Jade's AI Humanizer Milestone 1.

Tests:
1. Concurrency and Race Conditions (100 concurrent async calls)
2. Streaming Edge Cases & Vulnerabilities:
   - Chunk boundary buzzword splitting/leaking
   - Code fence placeholder corruption during streaming
3. Code Block Protection Integrity in post-processing:
   - Banned buzzwords inside code comments / strings
   - Code syntax corruption by grammar sanitizer
4. Edge Case Inputs:
   - Empty strings, pure whitespace, huge texts (100k chars), special chars, Unicode, CJK, Emoji
5. Token Estimator Accuracy:
   - Subword count for CJK / non-Latin scripts vs English
6. Fallback Model & Error Propagation:
   - Streaming generator missing fallback handling
   - Invalid API keys / API failure handling
7. Repeated Calls and Memory/State Leakage
"""

from __future__ import annotations

import asyncio
import time
import pytest
from unittest.mock import MagicMock, patch

from humanizer import Humanizer, HumanizeResult
from humanizer.engine.generator import GeminiGenerator
from humanizer.engine.prompt import estimate_prompt_tokens


# ==============================================================================
# 1. STREAMING VULNERABILITIES & FAILURE MODES
# ==============================================================================

def test_streaming_code_block_fragmentation_leak():
    """VULNERABILITY: If an LLM streams code fence placeholders across chunk boundaries,
    _restore_code_blocks fails to match, leaking raw placeholders and losing code.
    """
    async def _run():
        client = Humanizer(mock_mode=True)
        input_text = "Before code.\n```python\nprint('secret_code')\n```\nAfter code."

        # Simulate an async generator yielding chunks where placeholder is split
        async def mock_split_stream(prompt, system_instruction, temperature=0.7):
            # The prompt has '⟦CODE_FENCE_0⟧'
            yield "Before code. "
            yield "⟦CODE_"
            yield "FENCE_0⟧ "
            yield "After code."

        with patch.object(client.generator, "generate_stream_async", mock_split_stream):
            chunks = []
            async for c in client.humanize_stream(input_text):
                chunks.append(c)

            reconstructed = "".join(chunks)
            # The code fence MUST be restored, NOT leak raw placeholder
            assert "⟦CODE_" not in reconstructed, f"Leaked raw placeholder: {reconstructed}"
            assert "print('secret_code')" in reconstructed, f"Lost code block in stream: {reconstructed}"

    asyncio.run(_run())


def test_streaming_buzzword_chunk_boundary_leak():
    """VULNERABILITY: Multi-word buzzwords split across chunks bypass replace_banned_buzzwords."""
    async def _run():
        client = Humanizer(mock_mode=True)
        input_text = "Test split buzzword"

        async def mock_split_buzzwords(prompt, system_instruction, temperature=0.7):
            yield "In "
            yield "summary, we must examine this."

        with patch.object(client.generator, "generate_stream_async", mock_split_buzzwords):
            chunks = []
            async for c in client.humanize_stream(input_text):
                chunks.append(c)

            reconstructed = "".join(chunks)
            # 'In summary,' should be replaced with 'overall,' or 'in short,'
            assert "in summary" not in reconstructed.lower(), f"Banned buzzword leaked past stream: '{reconstructed}'"

    asyncio.run(_run())


def test_streaming_sync_fallback_model_success():
    """Verify generate_stream_sync seamlessly falls back to fallback_model on primary model failure."""
    generator = GeminiGenerator(api_key="fake_key", mock_mode=False)
    # When mock_mode is False, generator._client is initialized (if google-genai installed)
    if generator._client is not None:
        def mock_stream(model, contents, config):
            if model == "gemini-2.5-flash-lite":
                raise RuntimeError("Primary model quota exceeded")
            return [MagicMock(text="fallback success")]

        generator._client.models.generate_content_stream = mock_stream

        # Should fall back to fallback_model and yield chunks cleanly
        chunks = list(generator.generate_stream_sync("test", "instruction"))
        assert chunks == ["fallback success"]


def test_streaming_async_fallback_model_success():
    """Verify generate_stream_async seamlessly falls back to fallback_model on primary model failure."""
    async def _run():
        generator = GeminiGenerator(api_key="fake_key", mock_mode=False)
        if generator._client is not None:
            async def mock_async_stream(model, contents, config):
                if model == "gemini-2.5-flash-lite":
                    raise RuntimeError("Primary model quota exceeded")
                async def _gen():
                    yield MagicMock(text="async fallback success")
                return _gen()

            generator._client.aio.models.generate_content_stream = mock_async_stream

            chunks = []
            async for chunk in generator.generate_stream_async("test", "instruction"):
                chunks.append(chunk)
            assert chunks == ["async fallback success"]

    asyncio.run(_run())


# ==============================================================================
# 2. CODE BLOCK REWRITING BY GUARDRAILS IN POST-PROCESSING
# ==============================================================================

def test_code_block_guardrail_corruption_buzzwords_in_strings():
    """VULNERABILITY: client._post_process restores code blocks BEFORE calling
    replace_banned_buzzwords, causing strings and comments in user code to be corrupted.
    """
    client = Humanizer(mock_mode=True)
    code_input = (
        "Here is the program:\n\n"
        "```python\n"
        "# We must delve into the algorithm\n"
        "message = 'This is a tapestry of colors'\n"
        "```\n\n"
        "The code runs fine."
    )
    result = client.humanize(code_input, preserve_markdown=True)
    # The code block MUST NOT be modified at all!
    assert "# We must delve into the algorithm" in result.text, (
        f"Code comment was corrupted by guardrails:\n{result.text}"
    )
    assert "message = 'This is a tapestry of colors'" in result.text, (
        f"Code string literal was corrupted by guardrails:\n{result.text}"
    )


def test_code_block_guardrail_corruption_grammar_sanitizer():
    """VULNERABILITY: client._post_process restores code blocks BEFORE calling
    sanitize_and_verify_grammar, corrupting valid code syntax (spacing before commas, etc.).
    """
    client = Humanizer(mock_mode=True)
    code_input = (
        "Check this snippet:\n\n"
        "```python\n"
        "items = [1 , 2 , 3]\n"
        "```\n"
    )
    result = client.humanize(code_input, preserve_markdown=True)
    assert "[1 , 2 , 3]" in result.text, (
        f"Code syntax was modified by grammar sanitizer:\n{result.text}"
    )


# ==============================================================================
# 3. CONCURRENCY & ASYNC STRESS TESTING
# ==============================================================================

def test_concurrent_async_humanize_100_tasks():
    """STRESS: 100 concurrent async calls to humanize_async to verify thread/task safety."""
    async def _run():
        client = Humanizer(mock_mode=True)
        inputs = [f"Request number {i}: At this point in time, we must analyze the system." for i in range(100)]

        tasks = [client.humanize_async(inp, mode="budget", tone="casual") for inp in inputs]
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        for i, res in enumerate(results):
            assert isinstance(res, HumanizeResult)
            assert f"Request number {i}" in res.original_text
            assert "At this point in time" not in res.text
            assert res.prompt_tokens > 0

    asyncio.run(_run())


def test_concurrent_async_streaming_50_tasks():
    """STRESS: 50 concurrent async streams executing simultaneously."""
    async def _run():
        client = Humanizer(mock_mode=True)

        async def consume_stream(idx: int):
            inp = f"Stream task {idx} verifying real-time generation output."
            chunks = []
            async for chunk in client.humanize_stream(inp, mode="budget"):
                chunks.append(chunk)
            return "".join(chunks)

        tasks = [consume_stream(i) for i in range(50)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 50
        for res in results:
            assert len(res) > 0

    asyncio.run(_run())


# ==============================================================================
# 4. EDGE CASE INPUTS: HUGE TEXT, UNICODE, SPECIAL CHARACTERS
# ==============================================================================

def test_huge_text_handling_100k_chars():
    """STRESS: Verify handling of 100,000-character input (multi-page document)."""
    client = Humanizer(mock_mode=True)
    paragraph = (
        "In order to understand the complexity, due to the fact that modern software "
        "relies on microservices, we must evaluate each service independently. "
    )
    huge_text = (paragraph * 750)  # ~100,000 chars
    start_time = time.perf_counter()
    result = client.humanize(huge_text, mode="budget")
    duration = time.perf_counter() - start_time

    assert len(result.text) > 0
    assert "In order to" not in result.text
    # Should complete in reasonable time (< 3 seconds offline)
    assert duration < 3.0, f"Huge text processing took {duration:.2f}s, expected < 3.0s"


def test_special_characters_and_emojis():
    """EDGE CASE: Text containing emojis, math symbols, and non-ASCII punctuation."""
    client = Humanizer(mock_mode=True)
    special_text = (
        "🚀 Launching the AI Humanizer! 🔥 Features: π ≈ 3.14159, ∑(x) = 42. "
        "Moreover, we support «French quotes» and „German quotes“ & tabs\tand\rnewlines."
    )
    result = client.humanize(special_text, mode="budget")
    assert "🚀" in result.text
    assert "π ≈ 3.14159" in result.text
    assert "Moreover" not in result.text


def test_unicode_and_cjk_handling():
    """EDGE CASE: Non-Latin scripts (Chinese, Japanese, Arabic, Russian)."""
    client = Humanizer(mock_mode=True)
    cjk_text = (
        "人工智能正在改变世界。与此同时，我们需要保证文本的自然流畅。"
        "В то же время мы должны обеспечить естественность текста."
    )
    result = client.humanize(cjk_text, mode="budget")
    assert "人工智能" in result.text
    assert "В то же время" in result.text
    assert result.flesch_reading_ease >= 0.0


def test_token_counter_cjk_underestimation():
    """EDGE CASE / FINDING: estimate_prompt_tokens relies on whitespace splitting,
    severely undercounting CJK characters without spaces.
    """
    chinese_text = "人工智能正在快速改变世界各行各业的运作方式"  # 20 Chinese characters (~25-30 Gemini tokens)
    tokens = estimate_prompt_tokens(chinese_text)
    # In reality, 20 Chinese chars = ~20-30 tokens in Gemini BPE.
    # But estimate_prompt_tokens computes:
    # words = len(stripped.split()) = 1
    # chars = 20 -> chars / 4 = 5 tokens!
    assert tokens == 5, f"Observed tokens: {tokens}"
    # This proves a 4x-5x token underestimation for CJK languages!


# ==============================================================================
# 5. REPEATED CALLS & DETERMINISTIC PURITY
# ==============================================================================

def test_repeated_calls_idempotency_and_stability():
    """Verify that repeatedly humanizing text does not degrade or loop infinitely."""
    client = Humanizer(mock_mode=True)
    text = "In order to optimize operations, due to the fact that resources are scarce, we act."

    # Pass 1
    r1 = client.humanize(text, mode="deep", tone="casual")
    # Pass 2: humanizing the humanized text
    r2 = client.humanize(r1.text, mode="deep", tone="casual")

    assert len(r2.text) > 0
    assert "In order to" not in r2.text
    assert "due to the fact that" not in r2.text
    # Output should stabilize
    assert isinstance(r2.flesch_reading_ease, float)
