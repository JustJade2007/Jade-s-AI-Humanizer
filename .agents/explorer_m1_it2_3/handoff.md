# Milestone 1 Iteration 2 Handoff: Grammar Sanitizer & Generator Fallback

**Author**: `explorer_m1_it2_3` (`teamwork_preview_explorer`)  
**Target Milestone**: Milestone 1 Iteration 2 (Remediation Design)  
**Recipient**: Orchestrator & Worker  
**Date**: 2026-09-10T09:27:30Z  
**Type**: Hard Handoff (Investigation Complete)  

---

## 1. Observation

Direct empirical code inspection and pytest execution against `src/humanizer/engine/guardrails.py`, `src/humanizer/engine/generator.py`, and `tests/unit/test_adversarial_guardrails.py` revealed the following verbatim facts:

1. **Grammar Sanitizer Reduplication Corruption**:
   - `src/humanizer/engine/guardrails.py:259-263`:
     ```python
     redup_pattern = re.compile(r"\b([a-zA-Z]{2,})\s+\1\b", re.IGNORECASE)
     if redup_pattern.search(repaired):
         issues.append("Accidental word reduplication (stutter) detected.")
         repaired = redup_pattern.sub(r"\1", repaired)
     ```
   - Verbatim failure in `tests/unit/test_adversarial_guardrails.py::test_adversarial_grammar_does_not_corrupt_valid_reduplication`:
     ```
     AssertionError: Corrupted valid past perfect: She had a severe headache all morning.
     assert 'She had a severe headache all morning.' == 'She had had a severe headache all morning.'
     - She had had a severe headache all morning.
     + She had a severe headache all morning.
     ```
   - Verbatim failure in `tests/unit/test_adversarial_guardrails.py::test_adversarial_grammar_triple_stutter`:
     ```
     AssertionError: Stutter was not completely eliminated
     assert 'the the' not in 'We walked the the trail yesterday.'
     ```

2. **Grammar Sanitizer Wrongful Capitalization of Abbreviations**:
   - `src/humanizer/engine/guardrails.py:270-274`:
     ```python
     cap_pattern = re.compile(r"([.!?]\s+)([a-z])")
     if cap_pattern.search(repaired):
         issues.append("Sentence initial lowercase character detected.")
         repaired = cap_pattern.sub(_cap_match, repaired)
     ```
   - Direct execution check on `"We gathered supplies, e.g. pencils and paper."`:
     ```
     repaired: We gathered supplies, e.g. Pencils and paper.
     issues: ['Sentence initial lowercase character detected.']
     is_valid: False
     ```
   - `test_adversarial_guardrails.py:171-174` contained an assertion typo (`assert "e.g. Apples" not in res.repaired_text`) which masked that `"pencils"` was corrupted to `"Pencils"`.

3. **Grammar Sanitizer Missing Double Spaces Cleanup**:
   - `src/humanizer/engine/guardrails.py:222-286`: Zero handling for consecutive spaces.
   - Verbatim failure in `tests/unit/test_adversarial_guardrails.py::test_adversarial_grammar_double_spaces`:
     ```
     AssertionError: Double spaces were not repaired
     assert '  ' not in 'This  sentence  has  double  spaces  throughout.'
     ```

4. **Grammar Sanitizer Missing Unmatched Quotes Repair**:
   - `src/humanizer/engine/guardrails.py:222-286`: Zero checks or repairs for unmatched quotes.
   - Verbatim failure in `tests/unit/test_adversarial_guardrails.py::test_adversarial_grammar_unmatched_quotes`:
     ```
     AssertionError: Unmatched quote should be detected
     assert True is False
      + where True = GrammarVerificationResult(is_valid=True, issues=[], repaired_text='He said, "We need to fix this right now.').is_valid
     ```

5. **Generator Streaming Fallback Omission**:
   - `src/humanizer/engine/generator.py:177-237`: `generate_stream_sync` and `generate_stream_async` make raw calls to `self._client.models.generate_content_stream` without `try ... except` blocks, unlike `generate_sync` (lines 80-86) and `generate_async` (lines 140-145).
   - In `tests/unit/test_adversarial_engine.py:88-106`, `test_streaming_sync_missing_fallback_model` confirmed that a primary model quota exception crashes without attempting fallback to `self.fallback_model`.

---

## 2. Logic Chain

1. **Validity of English Grammatical Constructs (Observation 1)**:
   - English past-perfect constructions require the auxiliary verb "had" followed by the past participle "had" ("had had"). Demonstrative clauses require "that that". Geographical proper nouns like "Bora Bora" and "Pago Pago" are repetitive.
   - Replacing these with single words corrupts valid grammatical tense and meaning.
   - Introducing a whitelist `VALID_REDUPLICATIONS = frozenset({"had", "that", "bora", "pago", "walla", "baden", "sing", "aye", "dum", "yo"})` preserves valid occurrences while pattern `\b([a-zA-Z]{2,})(?:\s+\1)+\b` collapses stutters (including 3+ repetitions) into 1 word (or 2 for whitelisted words).

2. **Abbreviation Protection in Capitalization (Observation 2)**:
   - Standard punctuation heuristics assume `[.!?]\s+[a-z]` marks a sentence start.
   - However, abbreviations ending with periods (`e.g.`, `i.e.`, `etc.`, `vs.`, `al.`, `ca.`, `cf.`, `fig.`, `no.`, `dept.`, `approx.`, `inc.`, `ltd.`) do not terminate sentences.
   - By verifying whether the text immediately preceding the period matches `ABBREVIATION_PATTERN`, sentence capitalization can be safely skipped for abbreviations, preserving lowercase words following `e.g.` and `i.e.`.

3. **Whitespace and Quotation Normalization (Observations 3 and 4)**:
   - Double horizontal whitespace (`[ \t]{2,}`) can be collapsed to `" "` using `re.sub(r"[ \t]{2,}", " ", repaired)` without affecting markdown paragraph breaks (`\n\n`).
   - Unmatched double quotation marks (`repaired.count('"') % 2 != 0`) indicate a dangling quote that must be closed before line breaks, maintaining valid punctuation balance.

4. **Model Resilience in Streaming (Observation 5)**:
   - The primary Flash Lite model (`gemini-2.5-flash-lite`) can experience transient rate limits or outages.
   - Both `generate_sync` and `generate_async` recover by invoking `self.fallback_model` (`gemini-2.0-flash-lite`).
   - Symmetrically wrapping `generate_stream_sync` and `generate_stream_async` in `try ... except` (tracking `has_yielded` to prevent duplicating output if a mid-stream failure occurs) ensures zero-downtime streaming fallback.

---

## 3. Caveats

1. **Mid-Stream Partial Network Drop**:
   - If a streaming call fails after already yielding tokens to the client (e.g., chunk 10 of 20), falling back to token 0 of the secondary model would stream duplicated text. Thus, the implementation intentionally only triggers fallback when `not has_yielded`. Mid-stream network breaks re-raise the exception for the transport layer (SSE daemon) to handle.
2. **Single Quotes vs. Apostrophes**:
   - Single quotes (`'`) are heavily used in English contractions (`don't`, `it's`, `Jade's`). Attempting to balance single quotes based on parity creates massive false positives on any text containing an odd number of contractions. Quotation mark balancing is therefore strictly scoped to double quotes (`"`) and curly double quotes (`“`/`”`).
3. **Division of Labor**:
   - Buzzword regex boundaries, missing buzzwords (`nuanced`, `multi-faceted`), and subject-verb agreement in `guardrails.py` are addressed by peer `explorer_m1_it2_2`.
   - Client code block post-processing order and streaming buffer chunk reconstruction in `client.py` are addressed by peer `explorer_m1_it2_1`.

---

## 4. Conclusion

The remediation strategy for `guardrails.py` and `generator.py` is fully designed and documented with exact before/after code in:
`c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_m1_it2_3\remediation_grammar_generator.md`

### Actionable Specifications:
1. In `src/humanizer/engine/guardrails.py`:
   - Add `VALID_REDUPLICATIONS` and `ABBREVIATION_PATTERN`.
   - Update `sanitize_and_verify_grammar` to:
     - Check and balance unmatched double quotes (`"`).
     - Collapse double horizontal whitespace (`[ \t]{2,}` -> `" "`).
     - Handle reduplication via whitelist and multi-stutter reduction.
     - Preserve lowercase characters after common abbreviations (`e.g.`, `i.e.`).
2. In `src/humanizer/engine/generator.py`:
   - Wrap `generate_stream_sync` in `try ... except` with `has_yielded` tracking; fallback to `self.fallback_model`.
   - Wrap `generate_stream_async` in `try ... except` with `has_yielded` tracking; fallback to `self.fallback_model`.
3. In `tests/unit/test_adversarial_guardrails.py`:
   - Correct assertion typo on line 173 from `"e.g. Apples"` to `"e.g. Pencils"`.
4. In `tests/unit/test_adversarial_engine.py`:
   - Update `test_streaming_sync_missing_fallback_model` to verify that streaming fallback successfully yields from `self.fallback_model`.

---

## 5. Verification Method

To independently verify the proposed remediation once applied by the worker:

1. **Run Unit Guardrail Tests**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_guardrails.py -v
   ```
   *Expected*: All 8 baseline tests pass.

2. **Run Adversarial Guardrail Grammar Tests**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_guardrails.py -k "grammar or reduplication or abbreviation or spaces or quotes" -v
   ```
   *Expected*:
   - `test_adversarial_grammar_double_spaces` PASSED
   - `test_adversarial_grammar_unmatched_quotes` PASSED
   - `test_adversarial_grammar_triple_stutter` PASSED
   - `test_adversarial_grammar_does_not_corrupt_valid_reduplication` PASSED
   - `test_adversarial_grammar_does_not_corrupt_abbreviations` PASSED

3. **Run Adversarial Generator Streaming Fallback Tests**:
   ```powershell
   .\.venv\Scripts\python.exe -m pytest tests/unit/test_adversarial_engine.py -k "streaming_sync" -v
   ```
   *Expected*: `test_streaming_sync_fallback_model_success` PASSED.

4. **Invalidation Conditions**:
   - Any regression in baseline grammar tests (`test_guardrails.py`).
   - Any corruption of valid past-perfect ("had had") or demonstrative ("that that").
   - Any capitalization of words following "e.g." or "i.e.".
   - Unhandled exception when primary model fails during stream initiation.
