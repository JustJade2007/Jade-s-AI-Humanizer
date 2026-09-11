"""Benchmark tests strictly verifying <100 prompt tokens overhead in budget mode.

Acceptance Criteria:
- Automated benchmark test demonstrates budget mode operates under strict
  token overhead thresholds (<100 prompt tokens overhead per request).
"""

from __future__ import annotations

import pytest

from humanizer import Humanizer
from humanizer.engine.prompt import (
    estimate_prompt_tokens,
    get_budget_prompt,
)

TONES = ["neutral", "casual", "academic", "professional"]
READING_LEVELS = ["general", "middle_school", "high_school", "college"]


@pytest.mark.parametrize("tone", TONES)
@pytest.mark.parametrize("reading_level", READING_LEVELS)
def test_budget_mode_system_prompt_under_100_tokens(tone: str, reading_level: str):
    """Verify that every combination of style presets for budget mode produces <100 prompt tokens."""
    prompt = get_budget_prompt(tone=tone, reading_level=reading_level)
    token_count = estimate_prompt_tokens(prompt)

    # Strictly assert prompt token overhead is below 100 tokens
    assert token_count < 100, f"Overhead of {token_count} tokens exceeds strict 100-token limit for {tone}/{reading_level}"
    # Ensure safety margin: prompt should be well-optimized (typically 45-75 tokens)
    assert token_count < 85


def test_budget_mode_request_overhead_under_100_tokens():
    """Verify end-to-end Humanizer client request prompt overhead is strictly <100 tokens."""
    client = Humanizer(mock_mode=True)

    test_inputs = [
        "A brief short sentence.",
        (
            "This is a standard paragraph discussing system performance, database indexes, "
            "and query caching strategies. It contains approximately fifty words and evaluates "
            "how the humanizer operates under typical user workload conditions without adding "
            "unnecessary token bloat."
        ),
        (
            "Longer article section with multiple clauses. Machine learning systems often require "
            "substantial computational resources. When designing client-side tools, minimizing network "
            "payloads and API token overhead is essential for keeping operating expenses manageable "
            "while maintaining rapid response times."
        ),
    ]

    for tone in TONES:
        for text in test_inputs:
            result = client.humanize(text, mode="budget", tone=tone)
            raw_input_tokens = estimate_prompt_tokens(text)
            overhead = result.prompt_tokens - raw_input_tokens

            assert overhead < 100, (
                f"Client prompt overhead {overhead} exceeds strict 100 token threshold! "
                f"(Prompt tokens: {result.prompt_tokens}, Raw input: {raw_input_tokens})"
            )
