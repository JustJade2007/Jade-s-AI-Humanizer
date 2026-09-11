"""Unit tests for the thesaurus descriptor de-flating engine."""

import pytest
from humanizer.engine.thesaurus import deflate_descriptors
from humanizer import Humanizer


def test_deflate_confrontation_quiet_gravity():
    text = "Standing before the sculpture forces a confrontation with the quiet gravity of a history largely paved over by modern progress."
    deflated, replaced = deflate_descriptors(text)
    assert "forces a confrontation with" not in deflated.lower()
    assert "quiet gravity" not in deflated.lower()
    assert "modern progress" not in deflated.lower()
    assert len(replaced) > 0


def test_deflate_sentimental_contemplation():
    text = "My mind drifted to the impermanence of human footprints on the landscape. This piece feels burdened with remembrance."
    deflated, replaced = deflate_descriptors(text)
    assert "impermanence of human footprints" not in deflated.lower()
    assert "burdened with remembrance" not in deflated.lower()
    assert "heavy with memory" in deflated.lower()


def test_deflate_heritage_vulnerability():
    text = "The sculpture mirrors the vulnerability of the heritage it seeks to honor, noting the inclusion of a time capsule."
    deflated, replaced = deflate_descriptors(text)
    assert "mirrors the vulnerability" not in deflated.lower()
    assert "seeks to honor" not in deflated.lower()


def test_deflate_code_block_invariance():
    text = "Normal text forces a confrontation with reality.\n```python\n# forces a confrontation with the quiet gravity\nprint('paved over by modern progress')\n```"
    deflated, replaced = deflate_descriptors(text)
    assert "forces a confrontation with the quiet gravity" in deflated
    assert "paved over by modern progress" in deflated


def test_end_to_end_humanizer_deflates_descriptors():
    client = Humanizer(mock_mode=True)
    sample = (
        "Standing before Peter Toth's Whispering Giant forces a confrontation with the quiet gravity "
        "of a history largely paved over by modern progress. The piece is burdened with remembrance."
    )
    res = client.humanize(sample, mode="deep")
    assert "forces a confrontation with" not in res.text.lower()
    assert "quiet gravity" not in res.text.lower()
    assert "burdened with remembrance" not in res.text.lower()
