"""Benchmark tests strictly verifying 0 occurrences of banned AI buzzwords in output text.

Acceptance Criteria:
- Automated vocabulary audit scans output text and confirms 0 occurrences of banned AI buzzwords.
"""

from __future__ import annotations

import pytest

from humanizer import Humanizer
from humanizer.engine.guardrails import audit_vocabulary

HEAVILY_INFESTED_AI_SAMPLES = [
    (
        "Let us delve into this matter. It is crucial to remember that this technology serves as a testament "
        "to modern engineering. Moreover, the intricate tapestry of algorithms showcases a plethora of solutions. "
        "Furthermore, this pivotal discovery underscores a transformative paradigm shift in the realm of computing."
    ),
    (
        "In summary, the project seamlessly combines disparate modules. By and large, it acts as a beacon of "
        "innovation. Delving into the details reveals myriad possibilities that harness the full potential "
        "of our bespoke framework."
    ),
    (
        "In conclusion, we must meticulously examine every facet. The multifaceted interplay between components "
        "garners widespread praise, fostering an invaluable crucible for groundbreaking development."
    ),
]


@pytest.mark.parametrize("sample", HEAVILY_INFESTED_AI_SAMPLES)
@pytest.mark.parametrize("mode", ["budget", "deep"])
@pytest.mark.parametrize("tone", ["neutral", "casual", "academic", "professional"])
def test_zero_banned_buzzwords_in_output(sample: str, mode: str, tone: str):
    """Confirm zero banned AI buzzwords exist in humanized output across modes and tones."""
    client = Humanizer(mock_mode=True)

    # Initial sample must have violations before processing
    initial_violations = audit_vocabulary(sample)
    assert len(initial_violations) > 0, "Test sample must contain buzzwords to audit"

    # Humanize text
    result = client.humanize(sample, mode=mode, tone=tone)

    # Audit final humanized text: strictly 0 violations allowed
    final_violations = audit_vocabulary(result.text)
    assert final_violations == [], (
        f"Detected {len(final_violations)} banned AI buzzwords in output: {final_violations}\n"
        f"Output text:\n{result.text}"
    )

    # Ensure replaced buzzwords are accurately recorded in the metadata
    assert len(result.buzzwords_replaced) > 0
