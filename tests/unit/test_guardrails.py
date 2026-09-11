"""Unit tests for quality guardrails, vocabulary audit, and grammar sanitization."""

from __future__ import annotations

from humanizer.engine.guardrails import (
    audit_vocabulary,
    replace_banned_buzzwords,
    sanitize_and_verify_grammar,
)


def test_audit_vocabulary_clean_text():
    clean_text = "We built a simple web application using Python and SQLite to store user notes."
    violations = audit_vocabulary(clean_text)
    assert violations == []


def test_audit_vocabulary_detects_ai_buzzwords():
    ai_text = (
        "Let us delve into the multifaceted tapestry of modern technology. "
        "Moreover, this serves as a testament to our groundbreaking innovation. "
        "In summary, it provides a plethora of bespoke solutions."
    )
    violations = audit_vocabulary(ai_text)
    assert len(violations) >= 5
    lower_violations = [v.lower() for v in violations]
    assert any("delve" in v for v in lower_violations)
    assert any("tapestry" in v for v in lower_violations)
    assert any("moreover" in v for v in lower_violations)
    assert any("testament" in v for v in lower_violations)
    assert any("plethora" in v for v in lower_violations)


def test_replace_banned_buzzwords_and_case_preservation():
    input_text = "Moreover, we must delve into this issue. In summary, it is a testament to progress."
    cleaned, replaced = replace_banned_buzzwords(input_text)

    # Replaced list should track the modifications
    assert len(replaced) >= 3
    # Case must be preserved
    assert cleaned.startswith("Also,") or cleaned.startswith("Plus,")
    assert "Moreover" not in cleaned
    assert "delve into" not in cleaned
    assert "In summary" not in cleaned
    assert "testament" not in cleaned

    # Audit should now report 0 violations
    remaining_violations = audit_vocabulary(cleaned)
    assert remaining_violations == []


def test_grammar_spacing_before_punctuation():
    bad_punct = "We tested the components , and verified the system . It worked well !"
    result = sanitize_and_verify_grammar(bad_punct)

    assert result.is_valid is False
    assert "We tested the components, and verified the system. It worked well!" == result.repaired_text


def test_grammar_duplicate_commas():
    bad_commas = "We reviewed item one,, item two,,, and item three."
    result = sanitize_and_verify_grammar(bad_commas)

    assert result.is_valid is False
    assert ",," not in result.repaired_text
    assert ",,," not in result.repaired_text


def test_grammar_word_reduplication():
    stutter_text = "This was the the best outcome for for our project."
    result = sanitize_and_verify_grammar(stutter_text)

    assert result.is_valid is False
    assert "the the" not in result.repaired_text
    assert "for for" not in result.repaired_text
    assert "This was the best outcome for our project." == result.repaired_text


def test_grammar_sentence_capitalization():
    bad_caps = "here is the first idea. then we move to the next phase! finally, we succeed."
    result = sanitize_and_verify_grammar(bad_caps)

    assert result.is_valid is False
    assert result.repaired_text.startswith("Here is the first idea. Then we move to the next phase! Finally, we succeed.")


def test_grammar_code_fence_balance():
    unbalanced = "Here is some code:\n```python\nprint('hello')\n"
    result = sanitize_and_verify_grammar(unbalanced)

    assert result.is_valid is False
    assert result.repaired_text.count("```") % 2 == 0


def test_grammar_em_dash_removal_to_space():
    text_with_dash = "There is accountability—an unspoken reminder that land holds stories."
    result = sanitize_and_verify_grammar(text_with_dash)

    assert "—" not in result.repaired_text
    assert "accountability an unspoken reminder" in result.repaired_text

    text_with_spaced_dash = "Silence — a stark contrast — follows the noise."
    result2 = sanitize_and_verify_grammar(text_with_spaced_dash)
    assert "—" not in result2.repaired_text
    assert "Silence a stark contrast follows the noise." == result2.repaired_text
