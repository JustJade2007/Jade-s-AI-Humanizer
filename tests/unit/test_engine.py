"""Unit tests for Humanizer core engine, client, readability, and prompts."""

from __future__ import annotations

import asyncio
import pytest

from humanizer import Humanizer, HumanizeResult
from humanizer.engine.prompt import (
    estimate_prompt_tokens,
    get_budget_prompt,
    get_deep_prompt,
)
from humanizer.engine.readability import (
    calculate_flesch_kincaid_grade,
    calculate_flesch_reading_ease,
    calculate_readability,
    count_syllables,
)


def test_humanizer_init_mock_mode():
    client = Humanizer(mock_mode=True)
    assert client.generator.mock_mode is True


def test_humanize_sync_budget_mode():
    client = Humanizer(mock_mode=True)
    input_text = "The system is capable of processing requests due to the fact that it is optimized."
    result = client.humanize(input_text, mode="budget", tone="neutral")

    assert isinstance(result, HumanizeResult)
    assert result.mode == "budget"
    assert result.tone == "neutral"
    assert result.original_text == input_text
    assert len(result.text) > 0
    assert result.prompt_tokens > 0
    assert result.total_tokens >= result.prompt_tokens
    assert isinstance(result.flesch_reading_ease, float)
    assert isinstance(result.flesch_kincaid_grade, float)


def test_humanize_sync_deep_mode():
    client = Humanizer(mock_mode=True)
    input_text = "In order to understand the architecture, we have to analyze how the components interact."
    result = client.humanize(input_text, mode="deep", tone="casual", reading_level="high_school")

    assert isinstance(result, HumanizeResult)
    assert result.mode == "deep"
    assert result.tone == "casual"
    assert result.reading_level == "high_school"
    assert len(result.text) > 0
    assert "In order to" not in result.text


def test_humanize_async():
    async def _test():
        client = Humanizer(mock_mode=True)
        input_text = "At this point in time, it is evident that the solution provides significant benefits."
        result = await client.humanize_async(input_text, mode="budget", tone="professional")

        assert isinstance(result, HumanizeResult)
        assert result.mode == "budget"
        assert result.tone == "professional"
        assert len(result.text) > 0
        assert "At this point in time" not in result.text

    asyncio.run(_test())


def test_humanize_stream_async():
    async def _test():
        client = Humanizer(mock_mode=True)
        input_text = "This is a streaming test sentence designed to verify chunked generator output."
        chunks: list[str] = []

        async for chunk in client.humanize_stream(input_text, mode="budget"):
            chunks.append(chunk)

        assert len(chunks) > 0
        reconstructed = "".join(chunks)
        assert len(reconstructed) > 0

    asyncio.run(_test())


def test_humanize_stream_sync():
    client = Humanizer(mock_mode=True)
    input_text = "Synchronous streaming chunk verification test."
    chunks = list(client.humanize_stream_sync(input_text, mode="budget"))

    assert len(chunks) > 0
    assert len("".join(chunks)) > 0


def test_humanize_empty_string():
    client = Humanizer(mock_mode=True)
    result = client.humanize("", mode="budget")
    assert result.text == ""
    assert result.total_tokens == 0

    result_spaces = client.humanize("   \n\t  ", mode="deep")
    assert result_spaces.text == "   \n\t  "


def test_code_block_preservation():
    client = Humanizer(mock_mode=True)
    input_text = (
        "Here is the implementation of the algorithm:\n\n"
        "```python\n"
        "def delve_into_data(items):\n"
        "    # In order to process\n"
        "    return [x * 2 for x in items]\n"
        "```\n\n"
        "Moreover, this code executes rapidly."
    )
    result = client.humanize(input_text, mode="budget", preserve_markdown=True)

    # Code block inside ``` must remain exactly preserved
    assert "```python\ndef delve_into_data(items):\n    # In order to process\n    return [x * 2 for x in items]\n```" in result.text
    # But outside the code block, 'Moreover,' must be replaced
    assert "Moreover," not in result.text


def test_readability_calculations():
    simple_text = "The cat sat on the mat. The dog ran in the park. It was a sunny day."
    scores_simple = calculate_readability(simple_text)
    assert scores_simple["flesch_reading_ease"] > 80.0
    assert scores_simple["flesch_kincaid_grade"] < 5.0

    complex_text = (
        "Epistemological formulations concerning quantum electrodynamics necessitate "
        "comprehensive multidimensional computational paradigms to substantiate theoretical presuppositions."
    )
    scores_complex = calculate_readability(complex_text)
    assert scores_complex["flesch_reading_ease"] < 40.0
    assert scores_complex["flesch_kincaid_grade"] > 12.0

    assert calculate_flesch_reading_ease(simple_text) == scores_simple["flesch_reading_ease"]
    assert calculate_flesch_kincaid_grade(complex_text) == scores_complex["flesch_kincaid_grade"]


def test_syllable_counting_rules():
    assert count_syllables("cat") == 1
    assert count_syllables("water") == 2
    assert count_syllables("banana") == 3
    assert count_syllables("complexity") == 4
    assert count_syllables("unbelievable") >= 5

    # Silent 'e'
    assert count_syllables("rate") == 1
    assert count_syllables("bite") == 1
    assert count_syllables("simple") == 2  # '-le' ending

    # '-ed' endings
    assert count_syllables("looked") == 1
    assert count_syllables("walked") == 1
    assert count_syllables("started") == 2  # preceded by 't'
    assert count_syllables("needed") == 2   # preceded by 'd'

    # Empty / non-alpha
    assert count_syllables("") == 0
    assert count_syllables("123") == 0


def test_prompt_generation_and_tokens():
    budget_prompt = get_budget_prompt(tone="neutral", reading_level="general")
    tokens = estimate_prompt_tokens(budget_prompt)
    assert tokens < 100

    deep_prompt = get_deep_prompt(tone="casual", reading_level="middle_school")
    assert "conversational" in deep_prompt
    assert "middle school" in deep_prompt
