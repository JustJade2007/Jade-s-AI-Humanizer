# Milestone 1 Review & Adversarial Quality Report

**Reviewer**: `reviewer_m1_1` (`teamwork_preview_reviewer`)  
**Role**: Reviewer & Adversarial Critic  
**Target Milestone**: Milestone 1 (Core Engine & Guardrails)  
**Target Worker**: `worker_m1_1`  
**Date**: 2026-09-10T09:25:00Z  
**Verdict**: **REQUEST_CHANGES**  
**Integrity Status**: **CLEAN** (No integrity violations detected)  

---

## 1. Observation

Direct examination of the Milestone 1 codebase (`src/humanizer/client.py`, `src/humanizer/models.py`, `src/humanizer/engine/prompt.py`, `src/humanizer/engine/generator.py`, `src/humanizer/engine/deep.py`, `src/humanizer/engine/guardrails.py`, `src/humanizer/engine/readability.py`), unit tests, benchmarks, and E2E test contracts revealed the following verbatim observations:

### 1.1 Integrity & Logic Audit
- `src/humanizer/models.py:26-64`: Implements dataclasses `HumanizeResult` and `UsageMetadata` conforming to `PROJECT.md § Interface Contracts`. All required fields (`text`, `original_text`, `mode`, `tone`, `reading_level`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `buzzwords_replaced`, `flesch_reading_ease`) are typed and present.
- `src/humanizer/engine/readability.py:12-136`: Implements pure-Python phonetic syllable counting (`count_syllables`) with rules for silent 'e', '-ed', and '-es', along with regex markdown stripping (`_strip_markdown_and_code`) and Flesch Reading Ease / Flesch-Kincaid Grade Level formulas. No fake numbers or mocked scores.
- `src/humanizer/engine/prompt.py:12-59`: `BUDGET_BASE_INSTRUCTION` is 34 words (247 characters). Combined with tone and reading level directives, prompts evaluate to 41–42 words (306–317 characters). Token estimation evaluates to 76–80 tokens across all 16 configuration permutations, strictly `< 100` tokens.
- `src/humanizer/engine/deep.py:11-186`: `DeepParaphraser` implements genuine multi-layered transformations: 24 contraction mappings, 18 stiff transition mappings, paragraph/sentence splitting for burstiness variation, and code fence protection.
- `src/humanizer/engine/generator.py:24-237`: `GeminiGenerator` wraps official `google.genai` SDK with model fallback (`gemini-2.5-flash-lite` -> `gemini-2.0-flash-lite`) and offline token simulator when `mock_mode=True` or when `GEMINI_API_KEY` is not present.
- **Result**: Zero integrity violations found. No hardcoded test responses or facade stubs exist.

### 1.2 Code Block Restoration Timing Defect
- File: `src/humanizer/client.py:84-100`
  ```python
  # Restore code blocks first so guardrails don't rewrite code
  restored = self._restore_code_blocks(raw_output, fences)

  # 1. 0-tolerance banned AI buzzwords audit and replacement
  clean_text, buzzwords_replaced = replace_banned_buzzwords(restored)
  ...
  # 2. Automated syntax & grammar verification
  grammar_res = sanitize_and_verify_grammar(clean_text)
  ```
  Code blocks are restored *before* running `replace_banned_buzzwords` and `sanitize_and_verify_grammar`. Consequently, code comments, variable names, or strings containing buzzwords (e.g. `# delve into data`, `testament = True`) or formatting patterns (like `x : int = 5`, double commas `[1,, 2]`, or lowercase beginnings) will be rewritten by the guardrails inside the code block.

### 1.3 Missing Client Attributes on `Humanizer`
- File: `src/humanizer/client.py:22-42`
  ```python
  class Humanizer:
      def __init__(
          self,
          api_key: Optional[str] = None,
          model: str = "gemini-2.5-flash-lite",
          fallback_model: str = "gemini-2.0-flash-lite",
          mock_mode: bool = False,
      ) -> None:
          self.generator = GeminiGenerator(
              api_key=api_key,
              model=model,
              fallback_model=fallback_model,
              mock_mode=mock_mode,
          )
  ```
  `self.model`, `self.fallback_model`, `self.api_key`, and `self.mock_mode` are passed to `GeminiGenerator` but are NOT set on `self`.
  - In `tests/e2e/test_tier1_features.py:62-63`: `assert h.model in [...]` and `assert h.mock_mode is True` -> `AttributeError: 'Humanizer' object has no attribute 'model'`.
  - In `tests/e2e/test_tier1_features.py:94, 102`: `assert h.api_key == key` -> `AttributeError`.
  - In `tests/e2e/test_tier2_boundaries.py:96`: `assert h.fallback_model == "gemini-2.0-flash-lite"` -> `AttributeError`.

### 1.4 Subject-Verb Agreement Corruption in Verb Replacements
- File: `src/humanizer/engine/guardrails.py:137, 140`
  ```python
  (r"\bshowcases?\b", "displays"),
  (r"\bunderscores?\b", "highlights"),
  ```
  The regex `showcases?\b` matches both `showcase` and `showcases`, and unconditionally replaces both with 3rd-person singular `displays`.
  - `"They showcase their work"` -> `"They displays their work"` (broken grammar).
  - `"We underscore this point"` -> `"We highlights this point"` (broken grammar).

### 1.5 Detection vs. Replacement Asymmetries in Buzzwords
- File: `src/humanizer/engine/guardrails.py:35, 120-121`
  - `BANNED_AI_TERMS` detects plural `symphonies of`: `r"\bsymphon(?:y|ies)(?:\s+of)?\b"`.
  - `REPLACEMENT_RULES` only defines replacements for singular `symphony`:
    ```python
    (r"\bsymphony\s+of\b", "harmony of"),
    (r"\bsymphony\b", "concert"),
    ```
  - Result: Plural `symphonies` is never replaced by `replace_banned_buzzwords`, but `audit_vocabulary` detects it, producing an unresolvable audit failure.
- File: `src/humanizer/engine/guardrails.py:24, 71`
  - `BANNED_AI_TERMS` detects `r"\bserves?\s+as\s+a\s+(?:testament|reminder|beacon)\b"`.
  - `REPLACEMENT_RULES` only defines `(r"\bserves?\s+as\s+a\s+reminder\s+of\b", "reminds us of")`.
  - Result: Standalone `"serves as a reminder."` without trailing `"of"` is never replaced, but triggers an audit violation.

### 1.6 Omission of Mandated Buzzword "nuanced"
- `src/humanizer/engine/guardrails.py`: Pattern `nuanc` is completely absent from both `BANNED_AI_TERMS` and `REPLACEMENT_RULES`, despite being explicitly enumerated in the requirements.

### 1.7 Grammar Sanitizer Edge Cases
- File: `src/humanizer/engine/guardrails.py:259`
  - `redup_pattern = re.compile(r"\b([a-zA-Z]{2,})\s+\1\b", re.IGNORECASE)` corrupts valid English sentences:
    - `"She had had a cold."` -> `"She had a cold."` (past-perfect destroyed)
    - `"The fact that that occurred..."` -> `"The fact that occurred..."`
    - `"Bora Bora"` -> `"Bora"`
- File: `src/humanizer/engine/guardrails.py:270`
  - `cap_pattern = re.compile(r"([.!?]\s+)([a-z])")` capitalizes after abbreviations:
    - `"e.g. apples and oranges"` -> `"e.g. Apples and oranges"`
- Double spaces (`"  "`) and unmatched quotation marks are not checked or repaired by `sanitize_and_verify_grammar`.

---

## 2. Logic Chain

1. **Token Overhead and Core Contracts**:
   - `BUDGET_BASE_INSTRUCTION` (247 chars) + tone directive (30-34 chars) + reading level directive (23-32 chars) totals 306-317 chars (~42 words).
   - At ~4 chars/token, prompt overhead is strictly 76-80 tokens, safely fulfilling `< 100` prompt tokens overhead per request.
   - All 60 unit and benchmark tests created in `worker_m1_1` pass.
   - No integrity violations or fake facades were found.

2. **Root Cause of Post-Processing Vulnerabilities**:
   - Code blocks are meant to be 100% immune from modification (`PROJECT.md § Architecture`). By unmasking code blocks in `client._post_process` before passing text to `replace_banned_buzzwords` and `sanitize_and_verify_grammar`, code blocks are exposed to regex modifications. Restoring code blocks as the final post-processing step ensures complete immunity.
   - The regex replacement `r"\bshowcases?\b" -> "displays"` conflates singular and plural inflections, destroying subject-verb agreement. Splitting singular and plural rules fixes this directly.
   - The asymmetry between `BANNED_AI_TERMS` and `REPLACEMENT_RULES` causes `audit_vocabulary` to detect terms that `replace_banned_buzzwords` leaves behind, failing the zero-tolerance audit.

3. **Inter-Milestone Interface Compatibility**:
   - The E2E test suite created for the project expects `h.model`, `h.fallback_model`, `h.api_key`, and `h.mock_mode` directly on `Humanizer`. Exposing these attributes in `Humanizer.__init__` is trivial and prevents downstream test breakage.

---

## 3. Caveats

1. **Terminal Command Execution**:
   - Running terminal commands in this session encountered a permission prompt timeout. All observations and verification proofs are grounded in comprehensive AST inspection, exact line-by-line regex tracing, and verification against `tests/` source code and recorded test logs.
2. **Live Gemini API Key**:
   - All tests were reviewed using the deterministic offline mock engine since no live `GEMINI_API_KEY` was provided in the local environment.

---

## 4. Conclusion

**Verdict: REQUEST_CHANGES**

While the core architecture, token optimization (<100 tokens overhead), and basic happy-path unit tests are solid and clean of integrity violations, changes are required before Milestone 1 can be certified:

1. **Fix Code Block Restoration Timing**: Move `_restore_code_blocks` to the very end of `Humanizer._post_process` (after buzzword replacement and grammar sanitization).
2. **Expose Client Attributes on `Humanizer`**: Assign `self.model = model`, `self.fallback_model = fallback_model`, `self.api_key = api_key or os.getenv("GEMINI_API_KEY")`, and `self.mock_mode = self.generator.mock_mode` in `Humanizer.__init__`.
3. **Fix Subject-Verb Agreement in Verb Replacements**: Separate base and 3rd-person rules:
   - `r"\bshowcase\b" -> "display"`, `r"\bshowcases\b" -> "displays"`
   - `r"\bunderscore\b" -> "highlight"`, `r"\bunderscores\b" -> "highlights"`
4. **Resolve Buzzword Asymmetries & Add "nuanced"**:
   - Add `r"\bnuanc(?:e|es|ed|ing)\b"` to `BANNED_AI_TERMS` and replacement rules (`nuanced` -> `subtle`, `nuances` -> `subtleties`).
   - Add replacements for `symphonies of` -> `harmonies of`, `symphonies` -> `concerts`.
   - Add replacement for standalone `serves as a reminder` -> `reminds us`.
   - Support hyphenated `multi-faceted` in `BANNED_AI_TERMS` and `REPLACEMENT_RULES`.
5. **Harden Grammar Sanitizer**:
   - Whitelist valid reduplications: `{"had", "that"}`.
   - Ignore sentence capitalization after common abbreviations (`e.g.`, `i.e.`).
   - Add collapsing of multiple consecutive spaces (`re.sub(r"[ \t]{2,}", " ", repaired)`).

---

## 5. Verification Method

### 5.1 Independent Verification Script
Run the following Python snippet to verify all reported defects:
```python
from humanizer import Humanizer
from humanizer.engine.guardrails import audit_vocabulary, replace_banned_buzzwords, sanitize_and_verify_grammar

# 1. Verify Humanizer attributes
h = Humanizer(mock_mode=True)
assert hasattr(h, "model"), "Defect: h.model missing"
assert hasattr(h, "mock_mode"), "Defect: h.mock_mode missing"

# 2. Verify code block immunity from buzzwords
code_text = "Here is code:\n```python\n# This serves as a reminder\nx = 'delve into'\n```"
res = h.humanize(code_text, preserve_markdown=True)
assert "delve into" in res.text, "Defect: Code block content was modified by guardrails!"

# 3. Verify subject-verb agreement
clean, _ = replace_banned_buzzwords("They showcase their work.")
assert "They display " in clean, f"Defect: Broken subject-verb agreement: {clean}"

# 4. Verify buzzword symmetry
clean_sym, _ = replace_banned_buzzwords("The symphonies of sound.")
assert audit_vocabulary(clean_sym) == [], f"Defect: Unreplaced buzzword detected: {audit_vocabulary(clean_sym)}"

# 5. Verify valid reduplication preservation
gram = sanitize_and_verify_grammar("She had had a cold.")
assert "had had" in gram.repaired_text, f"Defect: Valid past-perfect corrupted: {gram.repaired_text}"
```

### 5.2 Test Invalidation Conditions
This verdict is invalidated and Milestone 1 can be APPROVED once:
1. `h.model`, `h.fallback_model`, `h.api_key`, and `h.mock_mode` are accessible on `Humanizer`.
2. Code blocks retain 100% byte-for-byte integrity even when code comments contain AI buzzwords.
3. Replacements preserve singular/plural verb agreements ("They display", not "They displays").
4. Zero buzzwords audit passes on `symphonies`, `serves as a reminder`, `multi-faceted`, and `nuanced`.
5. Grammar sanitizer preserves "had had" and "that that" while collapsing double spaces.
