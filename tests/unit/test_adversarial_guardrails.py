"""Adversarial stress tests for vocabulary guardrails, grammar sanitizer, and readability.

Empirical Challenger test suite testing:
1. Banned AI buzzwords eradication (capitalization, punctuation, hyphenation, pluralization, missing terms).
2. Grammar and syntax sanitizer (broken syntax, double spaces, stutters, unmatched quotes, valid text corruption).
3. Readability edge cases (empty strings, single words, numbers, markdown structures).
"""

from __future__ import annotations

import pytest

from humanizer.engine.guardrails import (
    audit_vocabulary,
    replace_banned_buzzwords,
    sanitize_and_verify_grammar,
)
from humanizer.engine.readability import calculate_readability, count_syllables


# ==============================================================================
# 1. BANNED AI BUZZWORDS & ERADICATION ADVERSARIAL TESTS
# ==============================================================================

def test_adversarial_missing_buzzword_nuanced():
    """Verify that 'nuanced' (explicitly cited in user prompt) is eradicated.
    
    FINDING: 'nuanced' and 'nuance' are currently absent from BANNED_AI_TERMS
    and REPLACEMENT_RULES.
    """
    text = "The committee presented a nuanced analysis of the policy."
    violations = audit_vocabulary(text)
    assert len(violations) > 0, "Expected 'nuanced' to be flagged as banned AI cliché"
    cleaned, replaced = replace_banned_buzzwords(text)
    assert "nuanced" not in cleaned.lower()
    assert audit_vocabulary(cleaned) == []


def test_adversarial_hyphenated_buzzwords():
    """Verify that hyphenated buzzwords like 'multi-faceted' are detected and replaced.
    
    FINDING: Word boundaries in \\bmultifaceted\\b fail to match 'multi-faceted'.
    """
    text = "The solution offers a multi-faceted approach to security."
    violations = audit_vocabulary(text)
    assert len(violations) > 0, "Expected 'multi-faceted' to be flagged"
    cleaned, replaced = replace_banned_buzzwords(text)
    assert "multi-faceted" not in cleaned.lower()
    assert audit_vocabulary(cleaned) == []


def test_adversarial_plural_symphonies_replacement():
    """Verify that plural 'symphonies' / 'symphonies of' are eradicated.
    
    FINDING: BANNED_AI_TERMS matches 'symphonies of', but REPLACEMENT_RULES
    only has 'symphony of' and 'symphony', leaving plural forms unreplaced.
    """
    text = "The forest echoed with symphonies of birdsong."
    violations = audit_vocabulary(text)
    assert len(violations) > 0, "Expected 'symphonies of' to be flagged"
    cleaned, replaced = replace_banned_buzzwords(text)
    # The cleaned text must not still contain banned terms
    remaining = audit_vocabulary(cleaned)
    assert remaining == [], f"Unreplaced buzzwords remaining: {remaining}"
    assert "symphonies" not in cleaned.lower()


def test_adversarial_serves_as_a_reminder_standalone():
    """Verify that 'serves as a reminder' without trailing 'of' is eradicated.
    
    FINDING: BANNED_AI_TERMS flags 'serves as a reminder', but REPLACEMENT_RULES
    only matches 'serves as a reminder of', leaving standalone form unreplaced.
    """
    text = "This monument serves as a reminder."
    violations = audit_vocabulary(text)
    assert len(violations) > 0, "Expected 'serves as a reminder' to be flagged"
    cleaned, replaced = replace_banned_buzzwords(text)
    remaining = audit_vocabulary(cleaned)
    assert remaining == [], f"Unreplaced buzzword remaining: {remaining}"
    assert "serves as a reminder" not in cleaned.lower()


def test_adversarial_markdown_underscore_italics_bypass():
    """Verify that buzzwords italicized with underscores are detected.
    
    FINDING: In Python regex, '_' is a word character (\\w). Hence, \\bdelve\\b
    does not match '_delve_' because there is no word boundary between '_' and 'd'.
    """
    text = "Let us _delve_ into the _tapestry_ of options."
    violations = audit_vocabulary(text)
    assert len(violations) >= 2, "Expected '_delve_' and '_tapestry_' to be flagged"
    cleaned, replaced = replace_banned_buzzwords(text)
    assert "delve" not in cleaned.lower()
    assert "tapestry" not in cleaned.lower()


def test_adversarial_subject_verb_agreement_corruption():
    """Verify that buzzword replacements do not corrupt subject-verb agreement.
    
    FINDING: (r'\\bshowcases?\\b', 'displays') and (r'\\bunderscores?\\b', 'highlights')
    unconditionally replace base-form verbs with 3rd-person singular verbs,
    corrupting valid plural subjects ('They displays', 'We highlights').
    """
    text = "They showcase their talents, while we underscore the importance."
    cleaned, _ = replace_banned_buzzwords(text)
    assert "they displays" not in cleaned.lower(), "Corrupted grammar: 'They displays'"
    assert "we highlights" not in cleaned.lower(), "Corrupted grammar: 'we highlights'"


# ==============================================================================
# 2. GRAMMAR & SYNTAX SANITIZER ADVERSARIAL TESTS
# ==============================================================================

def test_adversarial_grammar_double_spaces():
    """Verify that grammar sanitizer collapses extraneous double spaces.
    
    FINDING: sanitize_and_verify_grammar contains no check or repair for double spaces.
    """
    text = "This  sentence  has  double  spaces  throughout."
    res = sanitize_and_verify_grammar(text)
    assert "  " not in res.repaired_text, "Double spaces were not repaired"
    assert res.is_valid is False, "Double spaces should be flagged as an issue"


def test_adversarial_grammar_unmatched_quotes():
    """Verify that grammar sanitizer flags/repairs unmatched quotation marks.
    
    FINDING: sanitize_and_verify_grammar contains no check or repair for unmatched quotes.
    """
    text = 'He said, "We need to fix this right now.'
    res = sanitize_and_verify_grammar(text)
    assert res.is_valid is False, "Unmatched quote should be detected"
    assert res.repaired_text.count('"') % 2 == 0, "Unmatched quotes should be balanced"


def test_adversarial_grammar_triple_stutter():
    """Verify that stutter removal handles multiple repetitions (> 2).
    
    FINDING: Single-pass regex sub only reduces 'the the the' to 'the the'.
    """
    text = "We walked the the the trail yesterday."
    res = sanitize_and_verify_grammar(text)
    assert "the the" not in res.repaired_text, "Stutter was not completely eliminated"


def test_adversarial_grammar_does_not_corrupt_valid_reduplication():
    """Verify that valid English grammatical reduplication is NOT corrupted.
    
    FINDING: redup_pattern blindly strips 'had had' (valid past-perfect tense),
    'that that' (valid demonstrative pronoun), and proper nouns like 'Bora Bora'.
    """
    valid_text_1 = "She had had a severe headache all morning."
    res_1 = sanitize_and_verify_grammar(valid_text_1)
    assert res_1.repaired_text == valid_text_1, f"Corrupted valid past perfect: {res_1.repaired_text}"

    valid_text_2 = "The report confirmed that that outcome was unexpected."
    res_2 = sanitize_and_verify_grammar(valid_text_2)
    assert res_2.repaired_text == valid_text_2, f"Corrupted valid 'that that': {res_2.repaired_text}"

    valid_text_3 = "We vacationed in Bora Bora last summer."
    res_3 = sanitize_and_verify_grammar(valid_text_3)
    assert res_3.repaired_text == valid_text_3, f"Corrupted proper noun 'Bora Bora': {res_3.repaired_text}"


def test_adversarial_grammar_does_not_corrupt_abbreviations():
    """Verify that sentence capitalization doesn't capitalize after abbreviations like e.g., i.e.
    
    FINDING: cap_pattern matches [.!?]\\s+[a-z] after abbreviations like 'e.g. apples',
    capitalizing 'apples' to 'Apples'.
    """
    text = "We gathered supplies, e.g. pencils and paper."
    res = sanitize_and_verify_grammar(text)
    assert "e.g. Pencils" not in res.repaired_text, "Corrupted lowercase word after abbreviation"
    assert res.repaired_text == text
    assert res.is_valid is True


# ==============================================================================
# 3. READABILITY METRICS ADVERSARIAL TESTS
# ==============================================================================

def test_readability_empty_and_whitespace():
    """Verify readability metrics do not crash on empty or whitespace text."""
    res = calculate_readability("   \n\t  ")
    assert res["flesch_reading_ease"] == 100.0
    assert res["flesch_kincaid_grade"] == 0.0
    assert res["word_count"] == 0.0


def test_readability_numbers_and_symbols_only():
    """Verify readability metrics do not crash on non-alphabetic characters."""
    res = calculate_readability("12345 67890 @#$%^&* ()_+")
    assert res["flesch_reading_ease"] == 100.0
    assert res["flesch_kincaid_grade"] == 0.0


def test_readability_markdown_table_and_code_fence():
    """Verify that markdown code and tables are stripped without corrupting scores."""
    md_text = """
Here is a normal paragraph discussing software architecture. It has several words.

```python
def delve_into_nothing():
    return "tapestry"
```

| Col A | Col B |
|---|---|
| val1 | val2 |

Final concluding sentence that remains readable and simple.
"""
    res = calculate_readability(md_text)
    assert res["word_count"] > 0
    assert res["sentence_count"] > 0
    assert 0.0 <= res["flesch_kincaid_grade"] <= 20.0
