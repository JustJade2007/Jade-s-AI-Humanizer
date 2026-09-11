# Milestone 1 Challenger Report: Core Engine & Guardrails

**Date**: 2026-09-10T09:23:30Z  
**Challenger**: `challenger_m1_1` (`teamwork_preview_challenger`)  
**Target Milestone**: Milestone 1 (Core Engine & Guardrails)  
**Verdict**: **REJECT**

---

## 1. Observation

Empirical testing was conducted against the Milestone 1 codebase using:
Command: `$env:PYTHONPATH="src;.venv/Lib/site-packages"; python -m pytest tests/unit tests/benchmarks -v`

### Direct Test Results:
- **Baseline Worker Tests**: 60 passed (10 unit engine, 8 unit guardrail, 18 token overhead, 24 vocabulary audit).
- **Adversarial Engine & Guardrails Tests**: **14 FAILED, 72 PASSED** across all suites.

### Verbatim Failures and Code Observations:

1. **Code Block Modification in Post-Processing (Direct Violation of Requirement R3)**:
   - File: `src/humanizer/client.py`, lines 84–101:
     ```python
     # Restore code blocks first so guardrails don't rewrite code
     restored = self._restore_code_blocks(raw_output, fences)

     # 1. 0-tolerance banned AI buzzwords audit and replacement
     clean_text, buzzwords_replaced = replace_banned_buzzwords(restored)
     ...
     # 2. Automated syntax & grammar verification
     grammar_res = sanitize_and_verify_grammar(clean_text)
     final_text = grammar_res.repaired_text
     ```
   - Verbatim test failure (`tests/unit/test_adversarial_engine.py::test_code_block_guardrail_corruption_buzzwords_in_strings`):
     ```
     AssertionError: Code comment was corrupted by guardrails:
       Here is the program:
       
       ```python
       # We must explore the algorithm
       message = 'This is a blend of colors'
       ```
     assert '# We must delve into the algorithm' in ...
     ```
   - Verbatim test failure (`tests/unit/test_adversarial_engine.py::test_code_block_guardrail_corruption_grammar_sanitizer`):
     ```
     AssertionError: Code syntax was modified by grammar sanitizer:
       Check this snippet:
       
       ```python
       items = [1, 2, 3]
       ```
     assert '[1 , 2 , 3]' in ...
     ```

2. **Streaming Code Block Placeholder Fragmentation & Data Loss**:
   - File: `src/humanizer/client.py`, lines 229–234:
     ```python
     async for chunk in self.generator.generate_stream_async(payload_text, system_instruction):
         # If code fence placeholder in chunk, restore it
         restored_chunk = self._restore_code_blocks(chunk, fences)
         # Apply buzzword replacement
         clean_chunk, _ = replace_banned_buzzwords(restored_chunk)
         yield clean_chunk
     ```
   - Verbatim test failure (`tests/unit/test_adversarial_engine.py::test_streaming_code_block_fragmentation_leak`):
     ```
     AssertionError: Leaked raw placeholder: Before code. ⟦CODE_FENCE_0⟧ After code.
     assert '⟦CODE_' not in 'Before code. ⟦CODE_FENCE_0⟧ After code.'
     ```
   - When an LLM streams tokens splitting `⟦CODE_FENCE_0⟧` into e.g. `⟦CODE_` and `FENCE_0⟧`, neither chunk contains the full key; `_restore_code_blocks` fails to match, permanently leaking raw placeholder text and discarding the protected code block.

3. **Streaming Banned Buzzword Filter Bypass Across Chunk Boundaries**:
   - Verbatim test failure (`tests/unit/test_adversarial_engine.py::test_streaming_buzzword_chunk_boundary_leak`):
     ```
     AssertionError: Banned buzzword leaked past stream: 'In summary, we must examine this.'
     assert 'in summary' not in 'in summary, we must examine this.'
     ```
   - When multi-word phrases (such as `In summary`, `delve into`, `serves as a testament to`) span across streaming chunk boundaries, chunk-by-chunk regex matching fails to match, allowing banned AI buzzwords to leak directly to the client.

4. **Missing Fallback Model Handling in Streaming Methods**:
   - File: `src/humanizer/engine/generator.py`, lines 177–237:
     While `generate_sync` and `generate_async` have explicit `try ... except ... fallback to self.fallback_model`, `generate_stream_sync` and `generate_stream_async` call `self._client.models.generate_content_stream` directly without a `try ... except` block.
   - Verbatim test result (`tests/unit/test_adversarial_engine.py::test_streaming_sync_missing_fallback_model`):
     A failure in the primary streaming model propagates an unhandled `RuntimeError` without attempting fallback to `gemini-2.0-flash-lite`.

5. **Guardrail Grammar Corruption and Incomplete Buzzword Coverage**:
   - File: `src/humanizer/engine/guardrails.py`, lines 137–142, 258–263:
     - Plural subject-verb agreement corruption (`test_adversarial_subject_verb_agreement_corruption`): `showcases?` unconditionally replaces with `displays`, and `underscores?` with `highlights`, corrupting plural subjects into "They displays" and "We highlights".
     - Blind stutter reduplication removal (`test_adversarial_grammar_does_not_corrupt_valid_reduplication`): blindly replaces double words, corrupting valid past-perfect English ("She had had a severe headache" -> "She had a severe headache") and proper nouns ("Bora Bora" -> "Bora").
     - Underscore italics bypass (`test_adversarial_markdown_underscore_italics_bypass`): `\bdelve\b` fails to match `_delve_` because `_` is a `\w` character in Python regex.
     - Unreplaced terms: `symphonies of` and `serves as a reminder` (without trailing 'of') are flagged by `audit_vocabulary` but have no matching rules in `REPLACEMENT_RULES`, leaving unreplaced buzzwords in output.

---

## 2. Logic Chain

1. **Violation of Explicit Requirement R3 & Acceptance Criteria**:
   - Requirement R3 (`ORIGINAL_REQUEST.md` line 29) mandates: *"leaving code blocks completely untouched."*
   - Acceptance Criteria (`ORIGINAL_REQUEST.md` line 48) mandates: *"Markdown formatting benchmark verifies code blocks, bulleted lists, and headers remain structurally identical to source text."*
   - In `client.py`, line 84 notes `# Restore code blocks first so guardrails don't rewrite code`. However, calling `self._restore_code_blocks` on line 85 before `replace_banned_buzzwords` on line 88 and `sanitize_and_verify_grammar` on line 99 causes the restored code to pass through both filters.
   - Code comments, string literals, and code syntax inside fenced code blocks are actively rewritten (e.g., `delve into` rewritten to `explore`, `items = [1 , 2]` rewritten to `items = [1, 2]`).
   - Therefore, code blocks are NOT left completely untouched in Milestone 1.

2. **Fragility of Streaming Architecture**:
   - The streaming generator in `client.py` performs per-chunk placeholder restoration and per-chunk regex replacement.
   - Subword / token streaming naturally splits words and tokens across chunks.
   - Splitting `⟦CODE_FENCE_0⟧` drops code blocks entirely; splitting multi-word phrases bypasses the 0-tolerance buzzword policy.
   - Furthermore, unlike sync and async generation, streaming lacks fallback model execution.
   - Therefore, the streaming generator does not reliably support markdown preservation, buzzword filtering, or model fallback.

3. **Grammatical Regressions Introduced by Heuristic Sanitizer**:
   - A humanizer's core purpose is to make text sound natural and grammatically correct.
   - Replacing `showcase` with `displays` for plural subjects creates blatant grammatical errors ("They displays").
   - Stripping `had had` turns correct past-perfect sentences into past-simple, changing grammatical tense.
   - Leaving unreplaced buzzwords ("symphonies of", "serves as a reminder") contradicts the zero-tolerance claim.

---

## 3. Caveats

- **Live Gemini API Verification**: Live API calls against Google's servers with genuine API keys could not be executed because no `GEMINI_API_KEY` was provided in the local environment. All tests were executed using the deterministic offline mock engine and mock interfaces.
- **Concurrent Load**: Concurrency testing up to 100 async tasks passed cleanly without deadlocks, memory leaks, or race conditions.
- **Large Input Scaling**: Text processing up to 100,000 characters completed in under 1.5 seconds without crashing.

---

## 4. Conclusion

**Verdict: REJECT**

Milestone 1 cannot be approved in its current state due to two critical defects and three high-severity defects:
1. **Critical**: Code blocks are modified and corrupted during post-processing because they are restored before buzzword replacement and grammar sanitization (violates R3).
2. **Critical**: Streaming code block restoration fails under token chunking, leaking raw placeholder strings and losing code blocks.
3. **High**: Streaming buzzword replacement leaks multi-word buzzwords when split across chunk boundaries.
4. **High**: `generate_stream_sync` and `generate_stream_async` omit fallback model handling.
5. **High**: Heuristic grammar and replacement rules introduce grammatical errors (subject-verb mismatch, valid tense stripping).

### Required Remediation for Worker:
1. In `src/humanizer/client.py` (`_post_process`):
   - Keep code fence placeholders (`⟦CODE_FENCE_X⟧`) in place during `replace_banned_buzzwords` and `sanitize_and_verify_grammar`.
   - Restore code blocks (`_restore_code_blocks`) as the **very last step** of `_post_process`.
2. In `src/humanizer/client.py` (`humanize_stream` / `humanize_stream_sync`):
   - Implement a stream buffer / sliding window to reconstruct code fence placeholders and multi-word buzzwords across chunk boundaries before yielding.
3. In `src/humanizer/engine/generator.py`:
   - Implement `try ... except` fallback model logic for `generate_stream_sync` and `generate_stream_async`.
4. In `src/humanizer/engine/guardrails.py`:
   - Update `BANNED_AI_TERMS` and `REPLACEMENT_RULES` to support base vs. 3rd-person forms (e.g. `showcase` -> `display`, `showcases` -> `displays`).
   - Fix `_delve_` boundary matching by handling underscores as non-word delimiters.
   - Exclude legitimate past-perfect ("had had", "that that") and proper nouns from stutter reduction.
   - Add missing replacements for `symphonies of`, `serves as a reminder`, and hyphenated variants like `multi-faceted`.

---

## 5. Verification Method

To independently reproduce the failures:

1. Run the empirical adversarial engine test suite:
   ```powershell
   $env:PYTHONPATH="src;.venv/Lib/site-packages"
   python -m pytest tests/unit/test_adversarial_engine.py -v
   ```
   *Confirmed failures*:
   - `test_streaming_code_block_fragmentation_leak`
   - `test_streaming_buzzword_chunk_boundary_leak`
   - `test_code_block_guardrail_corruption_buzzwords_in_strings`
   - `test_code_block_guardrail_corruption_grammar_sanitizer`

2. Run the empirical adversarial guardrails test suite:
   ```powershell
   $env:PYTHONPATH="src;.venv/Lib/site-packages"
   python -m pytest tests/unit/test_adversarial_guardrails.py -v
   ```
   *Confirmed failures*: 10 failed tests including subject-verb agreement corruption, underscore boundary bypass, and past-perfect corruption.

3. Invalidation condition:
   All 14 adversarial tests must pass alongside the 60 existing unit/benchmark tests (74+ total passing tests) with 0 failures.
