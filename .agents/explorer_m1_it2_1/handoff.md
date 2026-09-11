# Handoff Report: Milestone 1 Iteration 2 Client Remediation Analysis

**Agent**: `explorer_m1_it2_1` (`teamwork_preview_explorer`)  
**Mission**: Analyze and design the exact fix strategy for `src/humanizer/client.py`  
**Target Milestone**: Milestone 1 Iteration 2 (Core Engine & Guardrails Remediation)  
**Date**: 2026-09-10T09:32:00Z  

---

## 1. Observation

Direct inspection of `src/humanizer/client.py`, test suites (`tests/unit/test_adversarial_engine.py`, `tests/e2e/test_tier1_features.py`, `tests/e2e/test_tier2_boundaries.py`, `tests/e2e/test_tier3_combinations.py`), and reports from `reviewer_m1_1` and `challenger_m1_1` revealed the following exact observations:

### 1.1 Inverted Code Block Restoration Timing
- **File**: `src/humanizer/client.py`, lines 84–101:
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
- **Verbatim Failure 1** (`tests/unit/test_adversarial_engine.py:34-45`):
  `test_code_block_guardrail_corruption_buzzwords_in_strings`:
  ```
  AssertionError: Code comment was corrupted by guardrails:
    Here is the program:
    ```python
    # We must explore the algorithm
    message = 'This is a blend of colors'
    ```
  assert '# We must delve into the algorithm' in ...
  ```
- **Verbatim Failure 2** (`tests/unit/test_adversarial_engine.py:46-55`):
  `test_code_block_guardrail_corruption_grammar_sanitizer`:
  ```
  AssertionError: Code syntax was modified by grammar sanitizer:
    Check this snippet:
    ```python
    items = [1 , 2 , 3]
    ```
  assert '[1 , 2 , 3]' in ...
  ```

### 1.2 Streaming Placeholder Fragmentation & Buzzword Leak
- **File**: `src/humanizer/client.py`, lines 229–234:
  ```python
  async for chunk in self.generator.generate_stream_async(payload_text, system_instruction):
      # If code fence placeholder in chunk, restore it
      restored_chunk = self._restore_code_blocks(chunk, fences)
      # Apply buzzword replacement
      clean_chunk, _ = replace_banned_buzzwords(restored_chunk)
      yield clean_chunk
  ```
- **Verbatim Failure 3** (`tests/unit/test_adversarial_engine.py:66-71`):
  `test_streaming_code_block_fragmentation_leak`:
  ```
  AssertionError: Leaked raw placeholder: Before code. ⟦CODE_FENCE_0⟧ After code.
  assert '⟦CODE_' not in 'Before code. ⟦CODE_FENCE_0⟧ After code.'
  ```
- **Verbatim Failure 4** (`tests/unit/test_adversarial_engine.py:72-85`):
  `test_streaming_buzzword_chunk_boundary_leak`:
  ```
  AssertionError: Banned buzzword leaked past stream: 'In summary, we must examine this.'
  assert 'in summary' not in 'in summary, we must examine this.'
  ```

### 1.3 Missing Client Attributes on `Humanizer`
- **File**: `src/humanizer/client.py`, lines 22–42:
  `__init__` passes `api_key`, `model`, `fallback_model`, and `mock_mode` to `GeminiGenerator`, but fails to assign them to `self`.
- **Verbatim Failures**:
  - `tests/e2e/test_tier1_features.py:62-63`: `assert h.model in [...]` and `assert h.mock_mode is True` -> `AttributeError: 'Humanizer' object has no attribute 'model'`
  - `tests/e2e/test_tier1_features.py:94, 102`: `assert h.api_key == key` -> `AttributeError: 'Humanizer' object has no attribute 'api_key'`
  - `tests/e2e/test_tier2_boundaries.py:96`: `assert h.fallback_model == "gemini-2.0-flash-lite"` -> `AttributeError: 'Humanizer' object has no attribute 'fallback_model'`

---

## 2. Logic Chain

1. **Code Block Protection**:
   - Project Requirement R3 mandates leaving code blocks completely untouched.
   - Restoring code blocks before `replace_banned_buzzwords` and `sanitize_and_verify_grammar` passes the unmasked code text directly into regular expressions designed for prose (changing `# delve into` to `# explore`, and collapsing spacing around commas).
   - Leaving placeholders (`⟦CODE_FENCE_X⟧`) in the text during guardrails and grammar sanitization shields the code contents.
   - Performing `_restore_code_blocks` as the **absolute last step** of `_post_process` guarantees 100% bit-for-bit code preservation.

2. **Streaming Integrity & Low Latency**:
   - LLM generation streams variable-sized token fragments. Any token boundary may cut across `⟦CODE_FENCE_0⟧` or multi-word buzzwords like `In summary,`.
   - Calling regex replace and code restoration per-chunk with zero buffer guarantees failure when tokens are split across chunks.
   - An accumulator class (`StreamChunkAccumulator`) with an internal buffer resolves this:
     - Detects complete placeholders and restores code fences directly without passing them through guardrails.
     - Detects partial placeholders (e.g. `⟦CODE_`) and holds them in the buffer until the closing bracket `⟧` arrives.
     - Evaluates safe prose boundaries (sentence boundaries or word boundaries not matching `BUZZWORD_STARTERS` or `BUZZWORD_INTERNAL_WORDS`) to emit prose continuously without latency, while never splitting a multi-word phrase.
     - Flushes all remaining text and placeholders cleanly at stream EOF.

3. **Client Contract Conformance**:
   - Setting `self.model = model`, `self.fallback_model = fallback_model`, `self.api_key = api_key or os.getenv("GEMINI_API_KEY")`, and `self.mock_mode = self.generator.mock_mode` in `Humanizer.__init__` satisfies all project contracts without breaking any existing behavior.

---

## 3. Caveats

1. **Read-Only Scope**: This report provides analysis, architectural design, and drop-in code specifications. Per role instructions, source files in `src/` were not modified directly.
2. **Companion Remediation in Guardrails and Generator**: While this analysis focuses on `src/humanizer/client.py`, companion fixes are required in `src/humanizer/engine/guardrails.py` (for subject-verb agreement and buzzword catalog symmetry) and `src/humanizer/engine/generator.py` (for fallback model handling in streaming).

---

## 4. Conclusion

The remediation strategy for `src/humanizer/client.py` is fully designed, specified, and ready for worker implementation:
1. **Move `_restore_code_blocks` to the end of `_post_process`** to guarantee complete code block immunity.
2. **Implement `StreamChunkAccumulator`** in `src/humanizer/client.py` to buffer partial placeholders and multi-word buzzwords across streaming chunks.
3. **Assign missing attributes on `Humanizer`** (`model`, `fallback_model`, `api_key`, `mock_mode`).

All detailed design rationale and complete drop-in code are documented in:
`c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_m1_it2_1\remediation_client.md`

---

## 5. Verification Method

### 5.1 Independent Test Suite
Run the following commands to verify that the remediation resolves the client failures:
```powershell
$env:PYTHONPATH="src;.venv/Lib/site-packages"
python -m pytest tests/unit/test_adversarial_engine.py -k "code_block or streaming" -v
```

### 5.2 Verification Script
```python
import asyncio
from unittest.mock import patch
from humanizer import Humanizer

# 1. Attribute Check
h = Humanizer(mock_mode=True)
assert hasattr(h, "model"), "h.model missing"
assert hasattr(h, "fallback_model"), "h.fallback_model missing"
assert hasattr(h, "api_key"), "h.api_key missing"
assert hasattr(h, "mock_mode"), "h.mock_mode missing"

# 2. Post-Process Code Block Immunity
code_text = "Prose before.\n```python\n# We must delve into data\nx = [1 , 2]\n```\nProse moreover."
res = h.humanize(code_text, preserve_markdown=True)
assert "# We must delve into data" in res.text, "Code comment altered!"
assert "x = [1 , 2]" in res.text, "Code syntax altered!"
assert "moreover" not in res.text.lower(), "Prose buzzword was not replaced!"

# 3. Streaming Placeholder & Buzzword Fragmentation
async def test_stream():
    async def mock_stream(prompt, instruction, temperature=0.7):
        yield "Start "
        yield "⟦CODE_"
        yield "FENCE_0⟧ "
        yield "In "
        yield "summary, end."

    with patch.object(h.generator, "generate_stream_async", mock_stream):
        chunks = []
        async for c in h.humanize_stream("Text\n```python\ncode()\n```\nMore"):
            chunks.append(c)
        full = "".join(chunks)
        assert "⟦CODE_" not in full, "Placeholder leaked!"
        assert "code()" in full, "Code lost!"
        assert "in summary" not in full.lower(), "Buzzword leaked!"

asyncio.run(test_stream())
print("All client remediation checks PASSED!")
```

### 5.3 Invalidation Conditions
This remediation plan is invalidated if:
1. Fenced code comments containing buzzwords (`# delve into`) are modified in `res.text`.
2. Streaming an artificially split placeholder (`⟦CODE_` + `FENCE_0⟧`) leaks the raw placeholder string or drops the code block.
3. Streaming an artificially split buzzword (`In ` + `summary`) yields `"in summary"`.
4. `Humanizer` instances lack `model`, `fallback_model`, `api_key`, or `mock_mode`.
