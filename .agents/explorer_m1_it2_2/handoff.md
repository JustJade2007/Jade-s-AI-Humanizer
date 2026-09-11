# Handoff Report: Guardrails Remediation Strategy (Milestone 1 Iteration 2)

**Author**: `explorer_m1_it2_2` (`teamwork_preview_explorer`)  
**Target Milestone**: Milestone 1 Iteration 2  
**Target Role**: Orchestrator / Worker (`worker_m1_2`)  
**Date**: 2026-09-10T09:30:00Z  
**Type**: Hard (Task Complete)  

---

## 1. Observation

Direct inspection of `src/humanizer/engine/guardrails.py`, `tests/unit/test_adversarial_guardrails.py`, `reviewer_m1_1/handoff.md`, and `challenger_m1_2/handoff.md` revealed the following exact observations:

### 1.1 Word Boundary & Formatting Bypass
- `src/humanizer/engine/guardrails.py:16`: `r"\bdelv(?:e|es|ed|ing)(?:\s+into)?\b"`
- `src/humanizer/engine/guardrails.py:26`: `r"\btapestr(?:y|ies)(?:\s+of)?\b"`
- `src/humanizer/engine/guardrails.py:40`: `r"\bmultifaceted\b"`
- `src/humanizer/engine/guardrails.py:104`: `(r"\bmultifaceted\b", "complex")`
- In Python's standard `re` engine, `\w` is `[a-zA-Z0-9_]`. In markdown text with underscore emphasis (e.g. `_delve_`, `_tapestry_`), `_` is a word character, so no `\b` word boundary exists between `_` and the alphabetic characters.
- In `python -c "import re; print(bool(re.search(r'\bdelve\b', '_delve_')))"`, output was `False`.
- In `python -c "import re; p = r'(?<![a-zA-Z0-9])delve(?![a-zA-Z0-9])'; print(bool(re.search(p, '_delve_'))); print(re.sub(p, 'dig', '_delve_'))"`, output was `True` and `_dig_`.
- For `multi-faceted`, the regex `\bmultifaceted\b` lacks optional hyphen matching (`multi[- ]?faceted`), so `multi-faceted` is ignored by both audit and replacement.

### 1.2 Missing Buzzwords & Asymmetries
- The mandated buzzword `nuanced` is completely absent from `BANNED_AI_TERMS` (lines 14-63) and `REPLACEMENT_RULES` (lines 66-159) across `src/humanizer/engine/guardrails.py`.
- `src/humanizer/engine/guardrails.py:35` flags `r"\bsymphon(?:y|ies)(?:\s+of)?\b"`, but lines 120-121 only define replacements for singular `symphony of` and `symphony`. Plural `symphonies of birdsong` is never replaced, leaving banned terms in output.
- `src/humanizer/engine/guardrails.py:24` flags `r"\bserves?\s+as\s+a\s+(?:testament|reminder|beacon)\b"`, but line 71 only replaces `r"\bserves?\s+as\s+a\s+reminder\s+of\b"`. When `of` is omitted (`"This serves as a reminder."`), replacement does not occur, but `audit_vocabulary` flags a violation.

### 1.3 Subject-Verb Agreement Defect
- `src/humanizer/engine/guardrails.py:137`: `(r"\bshowcases?\b", "displays")`
- `src/humanizer/engine/guardrails.py:140`: `(r"\bunderscores?\b", "highlights")`
- The `s?` quantifier matches both base form (`showcase`, `underscore`) and 3rd-person singular (`showcases`, `underscores`), unconditionally substituting singular verbs (`displays`, `highlights`). In `"They showcase their talents"`, the output is `"They displays their talents"`, corrupting valid English grammar.

### 1.4 Grammar Sanitizer Fragilities
- `src/humanizer/engine/guardrails.py:222-286`: No check or repair exists for multiple consecutive spaces (`"  "`) or unmatched double quotes (`"`).
- `src/humanizer/engine/guardrails.py:259`: `redup_pattern = re.compile(r"\b([a-zA-Z]{2,})\s+\1\b", re.IGNORECASE)` corrupts valid grammatical reduplications (`"had had"`, `"that that"`, `"Bora Bora"`). Furthermore, single-pass matching reduces `"the the the"` to `"the the"`.
- `src/humanizer/engine/guardrails.py:270`: `cap_pattern = re.compile(r"([.!?]\s+)([a-z])")` unconditionally capitalizes after punctuation, mutating `"e.g. pencils"` into `"e.g. Pencils"`.

---

## 2. Logic Chain

1. **Boundary Defect & Fix**:
   - `\b` depends on `\w`, which includes `_`. Therefore, markdown italics like `_delve_` fail `\b` detection (Observation 1.1).
   - Lookarounds `(?<![a-zA-Z0-9])` and `(?![a-zA-Z0-9])` treat markdown formatting (`_`, `*`, `~`) as delimiters while continuing to prevent partial matches in alphanumeric words (e.g. `shelved`, `adelve`).
   - Adding `[- ]?` to `multifaceted` ensures hyphenated and space-separated variants match.

2. **Buzzword Symmetry & Fix**:
   - Adding `rf"{_WB_LEFT}nuanc(?:e|es|ed|ing){_WB_RIGHT}"` and rules (`nuanced` -> `subtle`, `nuances` -> `subtleties`, `nuance` -> `subtlety`) satisfies the user requirement and closes the audit gap (Observation 1.2).
   - Adding `symphonies of` -> `harmonies of` and `symphonies` -> `concerts` restores symmetry with `BANNED_AI_TERMS`.
   - Adding standalone `serves? as a reminder` -> `reminds us` (placed after `serves? as a reminder of`) prevents unmatched trailing reminder sentences from causing audit failures.

3. **Subject-Verb Agreement Separation**:
   - Separating `showcase` -> `display` from `showcases` -> `displays` and `underscore` -> `highlight` from `underscores` -> `highlights` ensures plural/base subjects retain base-form verbs and 3rd-person singular subjects retain singular verbs (Observation 1.3).

4. **Grammar Sanitizer Hardening**:
   - Collapsing consecutive spaces with `re.sub(r" {2,}", " ", repaired)` and balancing quotes with parity checking resolves the missing checks (Observation 1.4).
   - Multi-repeat regex `(?:\s+\1)+` combined with whitelisting `{"had", "that", "bora"}` for count == 2 preserves valid grammatical structures while eradicating stutters.
   - Lookback checking for `COMMON_ABBREVIATIONS` prevents spurious capitalization after `e.g.`, `i.e.`, `etc.`.

---

## 3. Caveats

1. **Read-Only Explorer Scope**: In accordance with the Explorer archetype instructions, no source files were directly modified in this investigation. All remediation code, diffs, and catalogs are fully prepared in `.agents/explorer_m1_it2_2/remediation_guardrails.md`.
2. **Terminal Execution Constraints**: Terminal commands requiring interactive permission prompts were limited to prevent timeouts; regex behavior was verified via python one-liners and deterministic pattern proofs.
3. **Client-Side Code Block Order**: Full code block immunity also requires `client._post_process` in `src/humanizer/client.py` to restore code blocks *after* guardrail execution. This has been explicitly noted in the remediation document.

---

## 4. Conclusion

The guardrails implementation in `src/humanizer/engine/guardrails.py` requires surgical remediation across three primary areas and one secondary area:
1. **Formatting & Word Boundaries**: Replace `\b` with `_WB_LEFT` / `_WB_RIGHT` and support `multi[- ]?faceted`.
2. **Missing Buzzwords & Symmetry**: Add `nuanced` -> `subtle`, `symphonies of` -> `harmonies of`, and standalone `serves as a reminder` -> `reminds us`.
3. **Subject-Verb Agreement**: Disaggregate `showcase`/`showcases` and `underscore`/`underscores`.
4. **Grammar Sanitizer**: Add double space collapse, quote balancing, stutter loop, reduplication whitelist, and abbreviation check.

A complete, production-ready specification containing exact code replacement blocks has been authored in `.agents/explorer_m1_it2_2/remediation_guardrails.md`.

---

## 5. Verification Method

### 5.1 Independent Verification
Once implemented by the worker, verify against the adversarial test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_guardrails.py -v
```
Expected output: 100% pass across all 11 adversarial tests.

Also run existing unit tests and vocabulary audit benchmarks:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/unit/test_guardrails.py tests/benchmarks/test_vocabulary_audit.py -v
```
Expected output: 100% pass with 0 regressions.

### 5.2 Invalidation Conditions
This remediation plan is invalidated if:
1. Any markdown-wrapped buzzword (`_delve_`, `*tapestry*`) fails detection or corrupts outer markdown syntax.
2. `audit_vocabulary` flags any residual violation after `replace_banned_buzzwords` on `symphonies of` or `serves as a reminder`.
3. Sentences like `"They showcase their work"` produce `"They displays"`.
4. Valid reduplications like `"She had had a cold"` are mutated.
