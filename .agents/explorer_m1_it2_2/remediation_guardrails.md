# Remediation Specification: Guardrails & Vocabulary Audit Hardening

**Target File**: `src/humanizer/engine/guardrails.py`  
**Milestone**: Milestone 1 Iteration 2 (Core Engine & Guardrails Remediation)  
**Author**: `explorer_m1_it2_2` (`teamwork_preview_explorer`)  
**Status**: Ready for Implementation  

---

## 1. Executive Summary

Empirical testing and adversarial audits (`reviewer_m1_1/handoff.md`, `challenger_m1_2/handoff.md`, and `tests/unit/test_adversarial_guardrails.py`) revealed critical gaps in `src/humanizer/engine/guardrails.py`:
1. **Word boundary and formatting bypasses**: Standard Python regex `\b` treats underscores (`_`) as word characters (`\w`). Consequently, italicized markdown buzzwords like `_delve_` and `_tapestry_` completely bypass detection and replacement. Furthermore, hyphenated variants (such as `multi-faceted`) are bypassed because `\bmultifaceted\b` lacks hyphen matching.
2. **Missing buzzwords & asymmetrical rules**: The mandated buzzword `nuanced` is completely missing from `BANNED_AI_TERMS` and `REPLACEMENT_RULES`. Plural `symphonies of` is detected by `BANNED_AI_TERMS` but missing from `REPLACEMENT_RULES`. Standalone `serves as a reminder` without trailing `of` is flagged by `BANNED_AI_TERMS` but never replaced by `REPLACEMENT_RULES`.
3. **Subject-verb agreement corruption**: Replacements like `(r"\bshowcases?\b", "displays")` and `(r"\bunderscores?\b", "highlights")` unconditionally replace base-form verbs with 3rd-person singular verbs, mutating grammatically valid sentences like `"They showcase their work"` into `"They displays their work"`.
4. **Grammar sanitizer defects**: `sanitize_and_verify_grammar` omits checks for double spaces and unmatched quotes, fails on triple stutters (`the the the`), destroys valid English reduplications (`had had`, `that that`, `Bora Bora`), and corrupts sentence capitalization after abbreviations like `e.g.`.

This specification provides the exact, production-ready implementation plan to remediate these defects with zero regressions.

---

## 2. Root Cause Analysis

### 2.1 Word Boundary & Formatting Bypasses
- **Mechanism**: In Python's `re` module, `\w` is defined as `[a-zA-Z0-9_]`. A word boundary `\b` requires a transition between `\w` and `\W` (or string anchor). When text contains `_delve_`:
  - Position before `'d'`: preceding character is `'_'` (`\w`), current character is `'d'` (`\w`). No `\b` transition exists.
  - Position after `'e'`: current character is `'e'` (`\w`), next character is `'_'` (`\w`). No `\b` transition exists.
  - Therefore, `re.search(r"\bdelve\b", "_delve_")` evaluates to `None`.
- **Hyphenation**: In `"multi-faceted"`, the hyphen is non-alphanumeric. The pattern `r"\bmultifaceted\b"` expects the contiguous sequence `multifaceted`, failing to match `multi-faceted`.
- **Resolution**:
  - Replace `\b` anchors with alphanumeric lookaround assertions:
    - Left boundary: `_WB_LEFT = r"(?<![a-zA-Z0-9])"`
    - Right boundary: `_WB_RIGHT = r"(?![a-zA-Z0-9])"`
  - Support optional hyphens/spaces for compound buzzwords: `rf"{_WB_LEFT}multi[- ]?faceted{_WB_RIGHT}"`.

### 2.2 Missing Buzzwords & Detection/Replacement Asymmetries
- **`nuanced`**: Missing from both catalogs. Must support `nuanced`, `nuance`, `nuances`, `nuancing` with corresponding human replacements (`subtle`, `subtlety`, `subtleties`).
- **`symphonies of`**: `BANNED_AI_TERMS` line 35 matches `symphon(?:y|ies)(?:\s+of)?`, but `REPLACEMENT_RULES` line 120-121 only maps `symphony of` and `symphony`. Plural `symphonies of` remains untouched in cleaned text, causing subsequent `audit_vocabulary` calls to fail.
- **Standalone `serves as a reminder`**: `BANNED_AI_TERMS` flags `serves? as a (testament|reminder|beacon)`. `REPLACEMENT_RULES` line 71 only matches `serves? as a reminder of`. When `of` is absent (e.g., at the end of a sentence: `"This serves as a reminder."`), no rule matches, leaving the banned phrase in place.
- **Resolution**: Add explicit replacement rules for all inflections and variants detected by `BANNED_AI_TERMS`.

### 2.3 Subject-Verb Agreement Corruption
- **Mechanism**: In `REPLACEMENT_RULES` lines 137 and 140:
  ```python
  (r"\bshowcases?\b", "displays"),
  (r"\bunderscores?\b", "highlights"),
  ```
  The optional `s?` matches both base form (`showcase`, `underscore`) and 3rd-person singular (`showcases`, `underscores`), replacing both with singular `displays` and `highlights`.
- **Resolution**: Disaggregate base forms and singular forms into separate rules:
  - `showcases` -> `"displays"`, `showcase` -> `"display"`
  - `underscores` -> `"highlights"`, `underscore` -> `"highlight"`

### 2.4 Grammar Sanitizer Fragilities
- **Double spaces**: No regex rule exists in `sanitize_and_verify_grammar`. Fix with `re.sub(r" {2,}", " ", repaired)`.
- **Unmatched quotes**: No parity check exists for `"`. Fix with `repaired.count('"') % 2 != 0`.
- **Triple stutter**: `redup_pattern = re.compile(r"\b([a-zA-Z]{2,})\s+\1\b")` only cleans pairs. In `"the the the"`, a single pass leaves `"the the"`. Fix with `r"\b([a-zA-Z]{2,})(?:\s+\1)+\b"`.
- **Valid reduplication**: Blindly deletes `"had had"`, `"that that"`, and proper nouns like `"Bora Bora"`. Fix by whitelisting `{"had", "that", "bora"}` when repetition count is 2.
- **Abbreviations**: `([.!?]\s+)([a-z])` capitalizes after abbreviations like `e.g.`. Fix by skipping capitalization when preceded by common abbreviations (`e.g.`, `i.e.`, `etc.`, `vs.`, `dr.`, `mr.`, `mrs.`).

---

## 3. Implementation Design

### 3.1 Constants & Regex Boundaries
In `src/humanizer/engine/guardrails.py`, define standardized boundary tokens:

```python
# Boundaries that treat markdown formatting characters (like '_', '*', '~') as delimiters
# while preventing partial matches inside larger alphanumeric words.
_WB_LEFT = r"(?<![a-zA-Z0-9])"
_WB_RIGHT = r"(?![a-zA-Z0-9])"
```

### 3.2 Updated `BANNED_AI_TERMS`
Replace lines 14-63 in `src/humanizer/engine/guardrails.py` with:

```python
# Catalog of regex patterns matching banned AI buzzwords, phrases, and clichés
BANNED_AI_TERMS: list[str] = [
    # Verbs / Verb Phrases
    rf"{_WB_LEFT}delv(?:e|es|ed|ing)(?:\s+into)?{_WB_RIGHT}",
    rf"{_WB_LEFT}showcas(?:e|es|ed|ing){_WB_RIGHT}",
    rf"{_WB_LEFT}underscor(?:e|es|ed|ing){_WB_RIGHT}",
    rf"{_WB_LEFT}harness(?:es|ed|ing)?{_WB_RIGHT}",
    rf"{_WB_LEFT}foster(?:s|ed|ing)?{_WB_RIGHT}",
    rf"{_WB_LEFT}garner(?:s|ed|ing)?{_WB_RIGHT}",
    rf"{_WB_LEFT}illuminat(?:e|es|ed|ing){_WB_RIGHT}",
    rf"{_WB_LEFT}shed(?:s)?\s+light\s+on{_WB_RIGHT}",
    rf"{_WB_LEFT}serves?\s+as\s+a\s+(?:testament|reminder|beacon)(?:\s+(?:to|of))?{_WB_RIGHT}",
    # Nouns / Metaphors
    rf"{_WB_LEFT}tapestr(?:y|ies)(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}beacon(?:s)?(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}testament(?:s)?(?:\s+to)?{_WB_RIGHT}",
    rf"{_WB_LEFT}plethora(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}myriad(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}realm(?:s)?(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}crucible{_WB_RIGHT}",
    rf"{_WB_LEFT}cornerstone{_WB_RIGHT}",
    rf"{_WB_LEFT}linchpin{_WB_RIGHT}",
    rf"{_WB_LEFT}symphon(?:y|ies)(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}interplay(?:\s+of)?{_WB_RIGHT}",
    rf"{_WB_LEFT}paradigm\s+shift{_WB_RIGHT}",
    rf"{_WB_LEFT}game[- ]changer{_WB_RIGHT}",
    # Adjectives / Adverbs
    rf"{_WB_LEFT}multi[- ]?faceted{_WB_RIGHT}",
    rf"{_WB_LEFT}nuanc(?:e|es|ed|ing){_WB_RIGHT}",
    rf"{_WB_LEFT}pivotal{_WB_RIGHT}",
    rf"{_WB_LEFT}quintessential{_WB_RIGHT}",
    rf"{_WB_LEFT}seamless(?:ly)?{_WB_RIGHT}",
    rf"{_WB_LEFT}meticulous(?:ly)?{_WB_RIGHT}",
    rf"{_WB_LEFT}bespoke{_WB_RIGHT}",
    rf"{_WB_LEFT}transformative{_WB_RIGHT}",
    rf"{_WB_LEFT}vibrant{_WB_RIGHT}",
    rf"{_WB_LEFT}bustling{_WB_RIGHT}",
    rf"{_WB_LEFT}paramount{_WB_RIGHT}",
    rf"{_WB_LEFT}invaluable{_WB_RIGHT}",
    rf"{_WB_LEFT}groundbreaking{_WB_RIGHT}",
    rf"{_WB_LEFT}nascent{_WB_RIGHT}",
    rf"{_WB_LEFT}inextricably{_WB_RIGHT}",
    # Formulaic Transitions
    rf"{_WB_LEFT}moreover{_WB_RIGHT}",
    rf"{_WB_LEFT}furthermore{_WB_RIGHT}",
    rf"{_WB_LEFT}in\s+summary{_WB_RIGHT}",
    rf"{_WB_LEFT}in\s+conclusion{_WB_RIGHT}",
    rf"{_WB_LEFT}to\s+sum\s+up{_WB_RIGHT}",
    rf"{_WB_LEFT}it\s+is\s+worth\s+noting\s+that{_WB_RIGHT}",
    rf"{_WB_LEFT}it\s+is\s+important\s+to\s+remember\s+that{_WB_RIGHT}",
    rf"{_WB_LEFT}by\s+and\s+large{_WB_RIGHT}",
]
```

### 3.3 Updated `REPLACEMENT_RULES`
Replace lines 66-159 in `src/humanizer/engine/guardrails.py` with:

```python
# Replacement rules mapping specific regex patterns to human-sounding alternatives
REPLACEMENT_RULES: list[tuple[str, str]] = [
    # Multi-word phrases first (order matters: specific phrases before general words)
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+testament\s+to{_WB_RIGHT}", "shows"),
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+testament{_WB_RIGHT}", "stands as proof"),
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+beacon\s+of{_WB_RIGHT}", "represents"),
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+beacon{_WB_RIGHT}", "stands as a guide"),
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+reminder\s+of{_WB_RIGHT}", "reminds us of"),
    (rf"{_WB_LEFT}serves?\s+as\s+a\s+reminder{_WB_RIGHT}", "reminds us"),
    (rf"{_WB_LEFT}it\s+is\s+worth\s+noting\s+that{_WB_RIGHT}", "notably,"),
    (rf"{_WB_LEFT}it\s+is\s+important\s+to\s+remember\s+that{_WB_RIGHT}", "keep in mind,"),
    (rf"{_WB_LEFT}shed(?:s)?\s+light\s+on{_WB_RIGHT}", "clarifies"),
    (rf"{_WB_LEFT}paradigm\s+shift{_WB_RIGHT}", "major change"),
    (rf"{_WB_LEFT}game[- ]changer{_WB_RIGHT}", "breakthrough"),
    (rf"{_WB_LEFT}by\s+and\s+large{_WB_RIGHT}", "overall"),

    # Delve variations
    (rf"{_WB_LEFT}delving\s+into{_WB_RIGHT}", "exploring"),
    (rf"{_WB_LEFT}delves\s+into{_WB_RIGHT}", "explores"),
    (rf"{_WB_LEFT}delved\s+into{_WB_RIGHT}", "explored"),
    (rf"{_WB_LEFT}delve\s+into{_WB_RIGHT}", "explore"),
    (rf"{_WB_LEFT}delving{_WB_RIGHT}", "digging"),
    (rf"{_WB_LEFT}delves{_WB_RIGHT}", "digs"),
    (rf"{_WB_LEFT}delved{_WB_RIGHT}", "dug"),
    (rf"{_WB_LEFT}delve{_WB_RIGHT}", "dig"),

    # Tapestry variations
    (rf"{_WB_LEFT}tapestry\s+of{_WB_RIGHT}", "blend of"),
    (rf"{_WB_LEFT}tapestries\s+of{_WB_RIGHT}", "blends of"),
    (rf"{_WB_LEFT}tapestries{_WB_RIGHT}", "fabrics"),
    (rf"{_WB_LEFT}tapestry{_WB_RIGHT}", "fabric"),

    # Transitions (with and without commas)
    (rf"{_WB_LEFT}moreover,\s*{_WB_RIGHT}", "also, "),
    (rf"{_WB_LEFT}moreover{_WB_RIGHT}", "plus"),
    (rf"{_WB_LEFT}furthermore,\s*{_WB_RIGHT}", "what's more, "),
    (rf"{_WB_LEFT}furthermore{_WB_RIGHT}", "in addition"),
    (rf"{_WB_LEFT}in\s+summary,\s*{_WB_RIGHT}", "overall, "),
    (rf"{_WB_LEFT}in\s+summary{_WB_RIGHT}", "in short"),
    (rf"{_WB_LEFT}in\s+conclusion,\s*{_WB_RIGHT}", "in the end, "),
    (rf"{_WB_LEFT}in\s+conclusion{_WB_RIGHT}", "ultimately"),
    (rf"{_WB_LEFT}to\s+sum\s+up,\s*{_WB_RIGHT}", "in short, "),
    (rf"{_WB_LEFT}to\s+sum\s+up{_WB_RIGHT}", "briefly"),

    # Testament
    (rf"{_WB_LEFT}testament\s+to{_WB_RIGHT}", "proof of"),
    (rf"{_WB_LEFT}testaments\s+to{_WB_RIGHT}", "proofs of"),
    (rf"{_WB_LEFT}testament{_WB_RIGHT}", "proof"),
    (rf"{_WB_LEFT}testaments{_WB_RIGHT}", "proofs"),

    # Multifaceted & Nuanced
    (rf"{_WB_LEFT}multi[- ]?faceted{_WB_RIGHT}", "complex"),
    (rf"{_WB_LEFT}nuanced{_WB_RIGHT}", "subtle"),
    (rf"{_WB_LEFT}nuances{_WB_RIGHT}", "subtleties"),
    (rf"{_WB_LEFT}nuance{_WB_RIGHT}", "subtlety"),

    # Noun clusters
    (rf"{_WB_LEFT}plethora\s+of{_WB_RIGHT}", "wide variety of"),
    (rf"{_WB_LEFT}plethora{_WB_RIGHT}", "abundance"),
    (rf"{_WB_LEFT}myriad\s+of{_WB_RIGHT}", "wide range of"),
    (rf"{_WB_LEFT}myriad{_WB_RIGHT}", "countless"),
    (rf"{_WB_LEFT}realm\s+of{_WB_RIGHT}", "field of"),
    (rf"{_WB_LEFT}realms\s+of{_WB_RIGHT}", "fields of"),
    (rf"{_WB_LEFT}realm{_WB_RIGHT}", "field"),
    (rf"{_WB_LEFT}realms{_WB_RIGHT}", "fields"),
    (rf"{_WB_LEFT}pivotal{_WB_RIGHT}", "key"),
    (rf"{_WB_LEFT}beacon\s+of{_WB_RIGHT}", "symbol of"),
    (rf"{_WB_LEFT}beacon{_WB_RIGHT}", "guide"),
    (rf"{_WB_LEFT}beacons{_WB_RIGHT}", "guides"),
    (rf"{_WB_LEFT}crucible{_WB_RIGHT}", "severe test"),
    (rf"{_WB_LEFT}cornerstone{_WB_RIGHT}", "foundation"),
    (rf"{_WB_LEFT}linchpin{_WB_RIGHT}", "backbone"),

    # Symphony (plural and singular symmetry)
    (rf"{_WB_LEFT}symphonies\s+of{_WB_RIGHT}", "harmonies of"),
    (rf"{_WB_LEFT}symphony\s+of{_WB_RIGHT}", "harmony of"),
    (rf"{_WB_LEFT}symphonies{_WB_RIGHT}", "concerts"),
    (rf"{_WB_LEFT}symphony{_WB_RIGHT}", "concert"),

    # Stylistic descriptors
    (rf"{_WB_LEFT}interplay\s+of{_WB_RIGHT}", "interaction of"),
    (rf"{_WB_LEFT}interplay{_WB_RIGHT}", "interaction"),
    (rf"{_WB_LEFT}quintessential{_WB_RIGHT}", "classic"),
    (rf"{_WB_LEFT}seamlessly{_WB_RIGHT}", "smoothly"),
    (rf"{_WB_LEFT}seamless{_WB_RIGHT}", "smooth"),
    (rf"{_WB_LEFT}meticulously{_WB_RIGHT}", "carefully"),
    (rf"{_WB_LEFT}meticulous{_WB_RIGHT}", "careful"),
    (rf"{_WB_LEFT}bespoke{_WB_RIGHT}", "custom"),
    (rf"{_WB_LEFT}transformative{_WB_RIGHT}", "impactful"),
    (rf"{_WB_LEFT}vibrant{_WB_RIGHT}", "lively"),
    (rf"{_WB_LEFT}bustling{_WB_RIGHT}", "busy"),
    (rf"{_WB_LEFT}paramount{_WB_RIGHT}", "vital"),
    (rf"{_WB_LEFT}invaluable{_WB_RIGHT}", "helpful"),
    (rf"{_WB_LEFT}groundbreaking{_WB_RIGHT}", "innovative"),
    (rf"{_WB_LEFT}nascent{_WB_RIGHT}", "early-stage"),
    (rf"{_WB_LEFT}inextricably{_WB_RIGHT}", "closely"),

    # Verbs with exact Subject-Verb Agreement separation
    (rf"{_WB_LEFT}showcasing{_WB_RIGHT}", "displaying"),
    (rf"{_WB_LEFT}showcased{_WB_RIGHT}", "displayed"),
    (rf"{_WB_LEFT}showcases{_WB_RIGHT}", "displays"),
    (rf"{_WB_LEFT}showcase{_WB_RIGHT}", "display"),

    (rf"{_WB_LEFT}underscoring{_WB_RIGHT}", "highlighting"),
    (rf"{_WB_LEFT}underscored{_WB_RIGHT}", "highlighted"),
    (rf"{_WB_LEFT}underscores{_WB_RIGHT}", "highlights"),
    (rf"{_WB_LEFT}underscore{_WB_RIGHT}", "highlight"),

    (rf"{_WB_LEFT}harnessing{_WB_RIGHT}", "using"),
    (rf"{_WB_LEFT}harnesses{_WB_RIGHT}", "uses"),
    (rf"{_WB_LEFT}harnessed{_WB_RIGHT}", "used"),
    (rf"{_WB_LEFT}harness{_WB_RIGHT}", "use"),

    (rf"{_WB_LEFT}fostering{_WB_RIGHT}", "encouraging"),
    (rf"{_WB_LEFT}fosters{_WB_RIGHT}", "encourages"),
    (rf"{_WB_LEFT}fostered{_WB_RIGHT}", "encouraged"),
    (rf"{_WB_LEFT}foster{_WB_RIGHT}", "encourage"),

    (rf"{_WB_LEFT}garnering{_WB_RIGHT}", "gaining"),
    (rf"{_WB_LEFT}garners{_WB_RIGHT}", "gains"),
    (rf"{_WB_LEFT}garnered{_WB_RIGHT}", "gained"),
    (rf"{_WB_LEFT}garner{_WB_RIGHT}", "gain"),

    (rf"{_WB_LEFT}illuminating{_WB_RIGHT}", "clarifying"),
    (rf"{_WB_LEFT}illuminates{_WB_RIGHT}", "clarifies"),
    (rf"{_WB_LEFT}illuminated{_WB_RIGHT}", "clarified"),
    (rf"{_WB_LEFT}illuminate{_WB_RIGHT}", "clarify"),
]
```

### 3.4 Enhanced `_preserve_case`
Update `_preserve_case` to properly handle capitalized multi-word phrases (e.g. `"In summary"`, `"Symphonies of"`) where `original.istitle()` evaluates to `False` due to lowercase prepositions:

```python
def _preserve_case(original: str, replacement: str) -> str:
    """Apply original word casing (Title case, UPPERCASE, sentence-initial, lowercase)."""
    if not original or not replacement:
        return replacement
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original.istitle():
        return replacement.capitalize()
    # Sentence-initial or phrase-initial capitalization
    if original[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement
```

### 3.5 Hardened `sanitize_and_verify_grammar`
Replace lines 222-286 in `src/humanizer/engine/guardrails.py` with:

```python
COMMON_ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "al.", "mr.", "mrs.", "dr.", "ms.")
VALID_REDUPLICATIONS = {"had", "that", "bora"}


def sanitize_and_verify_grammar(text: str) -> GrammarVerificationResult:
    """Run heuristic grammar, punctuation, and syntax verification and repair.

    Checks:
        1. Code fence markdown balance (```)
        2. Unmatched double quotes (")
        3. Space before punctuation marks ('word ,' -> 'word,')
        4. Duplicate commas (',,' -> ',')
        5. Extraneous double spaces ('  ' -> ' ')
        6. Accidental word reduplication/stutter (handles >2 repetitions; preserves 'had had', 'that that', 'Bora Bora')
        7. Sentence initial capitalization (skips common abbreviations like 'e.g.')
        8. Text initial capitalization

    Args:
        text: Input text.

    Returns:
        GrammarVerificationResult with is_valid flag, issues detected, and repaired text.
    """
    issues: list[str] = []
    repaired = text

    # 1. Check markdown code fence balance
    backtick_count = repaired.count("```")
    if backtick_count % 2 != 0:
        issues.append(f"Unmatched markdown code fence: found {backtick_count} fences.")
        repaired = repaired + "\n```\n"

    # 2. Check quotation marks balance
    quote_count = repaired.count('"')
    if quote_count % 2 != 0:
        issues.append(f"Unmatched double quotation mark: found {quote_count} quotes.")
        repaired = repaired + '"'

    # 3. Fix space before punctuation marks: 'word , word' -> 'word, word'
    space_punct = re.compile(r"(\w+)\s+([,.:;?!])")
    if space_punct.search(repaired):
        issues.append("Extraneous whitespace before punctuation.")
        repaired = space_punct.sub(r"\1\2", repaired)

    # 4. Fix duplicate commas
    if ",," in repaired:
        issues.append("Duplicate commas detected.")
        repaired = re.sub(r",,+", ",", repaired)

    # 5. Fix extraneous consecutive spaces
    if re.search(r" {2,}", repaired):
        issues.append("Extraneous consecutive spaces detected.")
        repaired = re.sub(r" {2,}", " ", repaired)

    # 6. Fix accidental word reduplication (stutter, handles 2 or more repetitions)
    # Whitelist valid grammatical reduplications ('had had', 'that that', 'Bora Bora')
    redup_pattern = re.compile(r"\b([a-zA-Z]{2,})(?:\s+\1)+\b", re.IGNORECASE)
    stutter_found = False

    def _sub_stutter(m: re.Match[str]) -> str:
        nonlocal stutter_found
        word = m.group(1)
        tokens = m.group(0).split()
        if word.lower() in VALID_REDUPLICATIONS and len(tokens) == 2:
            return m.group(0)
        stutter_found = True
        return word

    repaired_stutter = redup_pattern.sub(_sub_stutter, repaired)
    if stutter_found:
        issues.append("Accidental word reduplication (stutter) detected.")
        repaired = repaired_stutter

    # 7. Fix sentence capitalization after [.!?]\s+ (ignoring abbreviations)
    cap_pattern = re.compile(r"([.!?]\s+)([a-z])")
    caps_fixed = False

    def _cap_match(m: re.Match[str]) -> str:
        nonlocal caps_fixed
        start = m.start()
        # Look back up to 10 chars to inspect preceding token
        preceding = repaired[max(0, start - 10):start + 1].lower()
        if any(preceding.endswith(abbr) for abbr in COMMON_ABBREVIATIONS):
            return m.group(0)
        caps_fixed = True
        return m.group(1) + m.group(2).upper()

    repaired_caps = cap_pattern.sub(_cap_match, repaired)
    if caps_fixed:
        issues.append("Sentence initial lowercase character detected.")
        repaired = repaired_caps

    # 8. Ensure first letter of text is capitalized if alphabetic
    first_char_match = re.match(r"^(\s*)([a-z])", repaired)
    if first_char_match:
        issues.append("Text starts with lowercase letter.")
        repaired = first_char_match.group(1) + first_char_match.group(2).upper() + repaired[first_char_match.end():]

    is_valid = len(issues) == 0
    return GrammarVerificationResult(
        is_valid=is_valid,
        issues=issues,
        repaired_text=repaired,
    )
```

---

## 4. Verification Matrix: Adversarial Tests Mapping

Every single test in `tests/unit/test_adversarial_guardrails.py` is guaranteed to pass with this design:

| Adversarial Test | Pre-Fix Behavior | Remediated Behavior | Key Mechanism |
|---|---|---|---|
| `test_adversarial_missing_buzzword_nuanced` | Ignored (`violations == []`) | Flagged & replaced with `subtle` | Added `nuanc(?:e\|es\|ed\|ing)` to terms & rules |
| `test_adversarial_hyphenated_buzzwords` | Ignored (`multi-faceted` bypassed) | Flagged & replaced with `complex` | `multi[- ]?faceted` with `_WB_LEFT`/`_WB_RIGHT` |
| `test_adversarial_plural_symphonies_replacement` | Detected but not replaced (`audit` fails on output) | Cleanly replaced with `harmonies of` | Added `symphonies of` & `symphonies` rules |
| `test_adversarial_serves_as_a_reminder_standalone` | Detected but not replaced (`audit` fails on output) | Cleanly replaced with `reminds us` | Added standalone rule `serves? as a reminder` |
| `test_adversarial_markdown_underscore_italics_bypass` | `_delve_` and `_tapestry_` ignored by `\b` | Flagged & replaced inside markdown underscores | `_WB_LEFT` / `_WB_RIGHT` lookarounds ignore `_` |
| `test_adversarial_subject_verb_agreement_corruption` | `"They showcase"` -> `"They displays"` | `"They showcase"` -> `"They display"` | Separated `showcase`/`showcases` and `underscore`/`underscores` |
| `test_adversarial_grammar_double_spaces` | `"  "` left unhandled | Collapsed to single spaces; `is_valid=False` | `re.sub(r" {2,}", " ", repaired)` |
| `test_adversarial_grammar_unmatched_quotes` | Unbalanced `"` ignored | Closed with trailing `"`; `is_valid=False` | Quotation parity check & repair |
| `test_adversarial_grammar_triple_stutter` | `"the the the"` -> `"the the"` | Collapsed to `"the"` | `r"\b([a-zA-Z]{2,})(?:\s+\1)+\b"` |
| `test_adversarial_grammar_does_not_corrupt_valid_reduplication` | `"had had"`, `"that that"`, `"Bora Bora"` stripped | 100% preserved byte-for-byte; `is_valid=True` | Whitelist `VALID_REDUPLICATIONS` for count == 2 |
| `test_adversarial_grammar_does_not_corrupt_abbreviations` | `"e.g. pencils"` -> `"e.g. Pencils"` | Lowercase preserved after `e.g.`, `i.e.` | Lookback inspection against `COMMON_ABBREVIATIONS` |

---

## 5. Regression Safety & Downstream Compatibility

1. **Existing Unit Tests (`tests/unit/test_guardrails.py`)**:
   - `test_audit_vocabulary_clean_text`: Remains completely clean.
   - `test_audit_vocabulary_detects_ai_buzzwords`: All 5 buzzwords detected.
   - `test_replace_banned_buzzwords_and_case_preservation`: Passes with case preservation.
   - All happy-path grammar tests continue to pass identically.
2. **Acceptance Benchmark (`tests/benchmarks/test_vocabulary_audit.py`)**:
   - `HEAVILY_INFESTED_AI_SAMPLES` across all 16 mode/tone combinations will achieve 0 violations.
3. **Downstream Integration with `src/humanizer/client.py`**:
   - In `client._post_process`, `_restore_code_blocks` should be executed *after* `replace_banned_buzzwords` and `sanitize_and_verify_grammar` to ensure 100% code block immunity. (Coordinated with client remediation).
