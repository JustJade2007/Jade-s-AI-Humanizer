# Remediation Strategy: Grammar Sanitizer & Generator Streaming Fallback

**Document**: `remediation_grammar_generator.md`  
**Author**: `explorer_m1_it2_3` (`teamwork_preview_explorer`)  
**Target Milestone**: Milestone 1 Iteration 2 (Remediation)  
**Target Files**:
- `src/humanizer/engine/guardrails.py` (`sanitize_and_verify_grammar`)
- `src/humanizer/engine/generator.py` (`generate_stream_sync`, `generate_stream_async`)
- `tests/unit/test_adversarial_guardrails.py`
- `tests/unit/test_adversarial_engine.py`

---

## 1. Executive Summary

Milestone 1 adversarial testing by `reviewer_m1_1`, `challenger_m1_1`, and `challenger_m1_2` uncovered critical defects in the heuristic grammar sanitizer and streaming generator:
1. **Grammar Sanitizer Deficiencies (`guardrails.py`)**:
   - Blind reduplication removal destroys valid English past-perfect constructions ("had had"), demonstrative relative clauses ("that that"), and proper nouns ("Bora Bora").
   - Blind reduplication pattern only reduces triple repetitions (`the the the`) to double (`the the`).
   - Sentence capitalization unconditionally capitalizes words following terminal punctuation (`[.!?]\s+`), corrupting valid abbreviations (e.g. `"e.g. pencils"` -> `"e.g. Pencils"`).
   - Double/multiple consecutive spaces (`"  "`) are completely unhandled and pass through uncorrected.
   - Unclosed/dangling quotation marks (`"`) are never flagged or balanced.
2. **Generator Streaming Fallback Deficiencies (`generator.py`)**:
   - `generate_stream_sync` and `generate_stream_async` make direct calls to `self._client.models.generate_content_stream` without `try ... except` fallback recovery, causing unhandled `RuntimeError` on primary model quotas or network blips, whereas `generate_sync` and `generate_async` seamlessly fall back to `self.fallback_model`.

This document provides the exact code transformations, rationale, and verification test cases to remediate both files.

---

## 2. Grammar Sanitizer Remediation (`src/humanizer/engine/guardrails.py`)

### 2.1 Root Cause Analysis

#### Defect A: Corrupting Valid Reduplication & Incomplete Stutter Reduction
- **Location**: `src/humanizer/engine/guardrails.py:259-263`
- **Current Code**:
  ```python
  redup_pattern = re.compile(r"\b([a-zA-Z]{2,})\s+\1\b", re.IGNORECASE)
  if redup_pattern.search(repaired):
      issues.append("Accidental word reduplication (stutter) detected.")
      repaired = redup_pattern.sub(r"\1", repaired)
  ```
- **Flaws**:
  1. *Valid English Destruction*: In English, consecutive identical words are grammatically required in past-perfect tense (*"She had had a severe headache"*) and demonstrative clauses (*"The report confirmed that that outcome was unexpected"*), as well as proper nouns (*"Bora Bora"*, *"Pago Pago"*). Blindly matching `\b([a-zA-Z]{2,})\s+\1\b` destroys tense and semantics.
  2. *Single-Pass Triple Stutter Leak*: For `"the the the"`, the match `\bthe\s+the\b` matches the first two words and replaces them with `"the"`, leaving the third word intact, producing `"the the"`.

#### Defect B: Wrongful Capitalization After Common Abbreviations
- **Location**: `src/humanizer/engine/guardrails.py:270-274`
- **Current Code**:
  ```python
  cap_pattern = re.compile(r"([.!?]\s+)([a-z])")
  if cap_pattern.search(repaired):
      issues.append("Sentence initial lowercase character detected.")
      repaired = cap_pattern.sub(_cap_match, repaired)
  ```
- **Flaw**:
  The regex treats any period followed by whitespace and a lowercase letter as a new sentence start. In phrases like `"We gathered supplies, e.g. pencils and paper."`, the period in `e.g.` triggers capitalization, corrupting `"pencils"` into `"Pencils"`.
- **Note on Existing Test Typo**: In `tests/unit/test_adversarial_guardrails.py:171-174`, the test asserted:
  `assert "e.g. Apples" not in res.repaired_text`
  while the test input text used `"pencils"`. The unremediated code actually turned `"pencils"` into `"Pencils"`. The assertion passed accidentally because `"Apples"` was absent, but `res.repaired_text` was corrupted and `res.is_valid` was incorrectly `False`! The remediation must fix the sanitizer logic and the test assertion should check that `"e.g. Pencils"` is NOT present and `res.repaired_text == text`.

#### Defect C: Missing Double Spaces Cleanup
- **Location**: `src/humanizer/engine/guardrails.py:222-286`
- **Flaw**: `sanitize_and_verify_grammar` contains no check or substitution for multiple consecutive horizontal spaces (`"  "`), violating Requirement R2 and failing `test_adversarial_grammar_double_spaces`.

#### Defect D: Missing Unmatched Quotes Repair
- **Location**: `src/humanizer/engine/guardrails.py:222-286`
- **Flaw**: `sanitize_and_verify_grammar` contains no check or repair for dangling quotation marks, failing `test_adversarial_grammar_unmatched_quotes`.

---

### 2.2 Proposed Implementation for `guardrails.py`

#### Module-Level Whitelists (Add to `src/humanizer/engine/guardrails.py`):
```python
# Whitelist of valid English reduplications (past-perfect, demonstratives, proper nouns)
VALID_REDUPLICATIONS: frozenset[str] = frozenset({
    "had",      # Past-perfect: "had had"
    "that",     # Demonstrative/relative: "that that"
    "bora",     # Proper noun: "Bora Bora"
    "pago",     # Proper noun: "Pago Pago"
    "walla",    # Proper noun: "Walla Walla"
    "baden",    # Proper noun: "Baden-Baden" / "Baden Baden"
    "sing",     # Proper noun: "Sing Sing"
    "aye",      # Idiom: "aye aye"
    "dum",      # Idiom: "dum dum"
    "yo",       # Idiom: "yo yo"
})

# Common abbreviations ending in period that do not terminate sentences
COMMON_ABBREVIATIONS: tuple[str, ...] = (
    "e.g", "i.e", "etc", "vs", "v", "al", "ca", "cf", "fig", "no", "dept", "approx", "inc", "ltd"
)
ABBREVIATION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(abbr) for abbr in COMMON_ABBREVIATIONS) + r")\.$",
    re.IGNORECASE,
)
```

#### Proposed `sanitize_and_verify_grammar`:
```python
def sanitize_and_verify_grammar(text: str) -> GrammarVerificationResult:
    """Run heuristic grammar, punctuation, and syntax verification and repair.

    Checks:
        1. Code fence markdown balance (```)
        2. Unmatched double quotation marks (")
        3. Double or multiple consecutive horizontal spaces ('  ' -> ' ')
        4. Extraneous space before punctuation marks (e.g. 'word , word' -> 'word, word')
        5. Duplicate commas (e.g. ',,' -> ',')
        6. Accidental word reduplication/stutter (with valid reduplication whitelist)
        7. Sentence initial capitalization after [.!?] (with abbreviation whitelist)
        8. Document initial letter capitalization

    Args:
        text: Input text.

    Returns:
        GrammarVerificationResult with is_valid flag, issues detected, and repaired text.
    """
    if not text:
        return GrammarVerificationResult(is_valid=True, issues=[], repaired_text=text)

    issues: list[str] = []
    repaired = text

    # 1. Check markdown code fence balance
    backtick_count = repaired.count("```")
    if backtick_count % 2 != 0:
        issues.append(f"Unmatched markdown code fence: found {backtick_count} fences.")
        repaired = repaired + "\n```\n"

    # 2. Check and balance unmatched double quotation marks
    if repaired.count('"') % 2 != 0:
        issues.append('Unmatched quotation mark (") detected.')
        if repaired.endswith("\n"):
            stripped = repaired.rstrip("\r\n")
            trailing = repaired[len(stripped):]
            repaired = stripped + '"' + trailing
        else:
            repaired = repaired + '"'

    # 3. Collapse double and multiple horizontal spaces: 'word  word' -> 'word word'
    double_spaces = re.compile(r"[ \t]{2,}")
    if double_spaces.search(repaired):
        issues.append("Extraneous consecutive whitespace detected.")
        repaired = double_spaces.sub(" ", repaired)

    # 4. Fix space before punctuation marks: 'word , word' -> 'word, word'
    space_punct = re.compile(r"(\w+)\s+([,.:;?!])")
    if space_punct.search(repaired):
        issues.append("Extraneous whitespace before punctuation.")
        repaired = space_punct.sub(r"\1\2", repaired)

    # 5. Fix duplicate commas: ',,' -> ','
    if ",," in repaired:
        issues.append("Duplicate commas detected.")
        repaired = re.sub(r",,+", ",", repaired)

    # 6. Fix accidental word reduplication (stutter) with whitelist and triple-stutter reduction
    redup_pattern = re.compile(r"\b([a-zA-Z]{2,})(?:\s+\1)+\b", re.IGNORECASE)
    stutter_found = False

    def _replace_reduplication(m: re.Match[str]) -> str:
        nonlocal stutter_found
        word = m.group(1)
        tokens = re.split(r"\s+", m.group(0))
        word_lower = word.lower()

        if word_lower in VALID_REDUPLICATIONS:
            if len(tokens) == 2:
                # Valid reduplication: "had had", "that that", "Bora Bora"
                return m.group(0)
            else:
                # Stutter of a valid word (3+ repetitions): reduce to 2
                stutter_found = True
                return f"{tokens[0]} {tokens[1]}"
        else:
            # Accidental stutter: reduce to 1
            stutter_found = True
            return tokens[0]

    repaired = redup_pattern.sub(_replace_reduplication, repaired)
    if stutter_found:
        issues.append("Accidental word reduplication (stutter) detected.")

    # 7. Fix sentence capitalization after [.!?]\s+ with abbreviation protection
    cap_detected = False

    def _cap_match(m: re.Match[str]) -> str:
        nonlocal cap_detected
        prefix = m.group(1)
        char = m.group(2)

        # Only period (.) can be an abbreviation, not ! or ?
        first_punct = prefix.strip()[0]
        if first_punct == ".":
            # Check if text immediately preceding the period is a known abbreviation
            preceding_text = m.string[:m.start() + 1]
            if ABBREVIATION_PATTERN.search(preceding_text):
                # Preceded by abbreviation like 'e.g.' or 'i.e.' -> leave lowercase
                return m.group(0)

        cap_detected = True
        return prefix + char.upper()

    cap_pattern = re.compile(r"([.!?]\s+)([a-z])")
    repaired = cap_pattern.sub(_cap_match, repaired)
    if cap_detected:
        issues.append("Sentence initial lowercase character detected.")

    # 8. Ensure first letter of text is capitalized if alphabetic
    first_char_match = re.match(r"^(\s*)([a-z])", repaired)
    if first_char_match:
        issues.append("Text starts with lowercase letter.")
        repaired = (
            first_char_match.group(1)
            + first_char_match.group(2).upper()
            + repaired[first_char_match.end():]
        )

    is_valid = len(issues) == 0
    return GrammarVerificationResult(
        is_valid=is_valid,
        issues=issues,
        repaired_text=repaired,
    )
```

---

## 3. Streaming Fallback Remediation (`src/humanizer/engine/generator.py`)

### 3.1 Root Cause Analysis
- **Location**: `src/humanizer/engine/generator.py:177-237`
- **Current Behavior**:
  - `generate_sync` (lines 80–86) and `generate_async` (lines 140–145) wrap the primary call in `try ... except Exception: return self._call_gemini_*(self.fallback_model, ...)` to ensure automatic resilience when `gemini-2.5-flash-lite` has rate limits or outages.
  - In contrast, `generate_stream_sync` and `generate_stream_async` call `self._client.models.generate_content_stream` directly with no `try ... except`.
  - When the primary model raises an exception (e.g. quota exceeded, network timeout), the stream crashes immediately, failing `test_streaming_sync_missing_fallback_model`.

### 3.2 Key Design Considerations for Streaming Fallback
1. **Fallback Timing**: Fallback to `self.fallback_model` should occur if the primary model fails before yielding chunks (initial handshake, quota check, auth failure, prompt rejection). If the primary model fails mid-stream after chunks have already been yielded, restarting from token 0 would yield duplicated text to the client; thus we track `has_yielded` and only switch models if `not has_yielded`.
2. **Model Identity**: Ensure fallback is only attempted when `self.fallback_model` is defined and differs from `self.model`.
3. **Async Streaming Stream Handling**: In `generate_stream_async`, both the `await client.aio.models.generate_content_stream(...)` call and the `async for chunk in stream` iteration must be protected.

---

### 3.3 Proposed Implementation for `generator.py`

#### Proposed `generate_stream_sync`:
```python
    def generate_stream_sync(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        """Stream chunks synchronously with automatic fallback model recovery."""
        if self.mock_mode or self._client is None:
            full_text = self._offline_transform(prompt, system_instruction)
            # Yield in realistic word-group chunks
            words = full_text.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i : i + 3])
                if i + 3 < len(words):
                    chunk += " "
                yield chunk
            return

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        has_yielded = False
        try:
            stream = self._client.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            for chunk in stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
        except Exception:
            if not has_yielded and self.fallback_model and self.fallback_model != self.model:
                fallback_stream = self._client.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=prompt,
                    config=config,
                )
                for chunk in fallback_stream:
                    if chunk.text:
                        yield chunk.text
            else:
                raise
```

#### Proposed `generate_stream_async`:
```python
    async def generate_stream_async(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream chunks asynchronously (for SSE / FastAPI endpoints) with model fallback."""
        if self.mock_mode or self._client is None:
            full_text = self._offline_transform(prompt, system_instruction)
            words = full_text.split(" ")
            for i in range(0, len(words), 3):
                chunk = " ".join(words[i : i + 3])
                if i + 3 < len(words):
                    chunk += " "
                await asyncio.sleep(0.01)
                yield chunk
            return

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        has_yielded = False
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=config,
            )
            async for chunk in stream:
                if chunk.text:
                    has_yielded = True
                    yield chunk.text
        except Exception:
            if not has_yielded and self.fallback_model and self.fallback_model != self.model:
                fallback_stream = await self._client.aio.models.generate_content_stream(
                    model=self.fallback_model,
                    contents=prompt,
                    config=config,
                )
                async for chunk in fallback_stream:
                    if chunk.text:
                        yield chunk.text
            else:
                raise
```

---

## 4. Test Suite Alignment

### 4.1 Update `tests/unit/test_adversarial_engine.py`
In `test_adversarial_engine.py:88-106`, update `test_streaming_sync_missing_fallback_model` to verify that fallback succeeds:
```python
def test_streaming_sync_fallback_model_success():
    """Verify generate_stream_sync seamlessly falls back to fallback_model on primary model failure."""
    generator = GeminiGenerator(api_key="fake_key", mock_mode=False)
    if generator._client is not None:
        def mock_stream(model, contents, config):
            if model == "gemini-2.5-flash-lite":
                raise RuntimeError("Primary model quota exceeded")
            return [MagicMock(text="fallback success")]

        generator._client.models.generate_content_stream = mock_stream

        # Should fall back to fallback_model and yield chunks cleanly
        chunks = list(generator.generate_stream_sync("test", "instruction"))
        assert chunks == ["fallback success"]


@pytest.mark.asyncio
async def test_streaming_async_fallback_model_success():
    """Verify generate_stream_async seamlessly falls back to fallback_model on primary model failure."""
    generator = GeminiGenerator(api_key="fake_key", mock_mode=False)
    if generator._client is not None:
        async def mock_async_stream(model, contents, config):
            if model == "gemini-2.5-flash-lite":
                raise RuntimeError("Primary model quota exceeded")
            async def _gen():
                yield MagicMock(text="async fallback success")
            return _gen()

        generator._client.aio.models.generate_content_stream = mock_async_stream

        chunks = []
        async for chunk in generator.generate_stream_async("test", "instruction"):
            chunks.append(chunk)
        assert chunks == ["async fallback success"]
```

### 4.2 Fix Typo in `tests/unit/test_adversarial_guardrails.py`
Line 173 of `test_adversarial_guardrails.py` should be corrected from:
```python
    assert "e.g. Apples" not in res.repaired_text, "Corrupted lowercase word after abbreviation"
```
to:
```python
    assert "e.g. Pencils" not in res.repaired_text, "Corrupted lowercase word after abbreviation"
    assert res.repaired_text == text
    assert res.is_valid is True
```

---

## 5. Verification Matrix

| Test Name | Target Behavior | Expected Result |
|---|---|---|
| `test_adversarial_grammar_double_spaces` | `"This  sentence  has  double  spaces."` | Converted to `"This sentence has double spaces."`, `is_valid == False` |
| `test_adversarial_grammar_unmatched_quotes` | `'He said, "We need to fix this right now.'` | Converted to `'He said, "We need to fix this right now."'`, `count('"') % 2 == 0` |
| `test_adversarial_grammar_triple_stutter` | `"We walked the the the trail yesterday."` | Converted to `"We walked the trail yesterday."`, `"the the" not in text` |
| `test_adversarial_grammar_does_not_corrupt_valid_reduplication` | `"She had had a severe headache all morning."` | Repaired text matches input identically, `is_valid == True` |
| `test_adversarial_grammar_does_not_corrupt_valid_reduplication` | `"The report confirmed that that outcome was unexpected."` | Repaired text matches input identically, `is_valid == True` |
| `test_adversarial_grammar_does_not_corrupt_valid_reduplication` | `"We vacationed in Bora Bora last summer."` | Repaired text matches input identically, `is_valid == True` |
| `test_adversarial_grammar_does_not_corrupt_abbreviations` | `"We gathered supplies, e.g. pencils and paper."` | Repaired text matches input identically, `"e.g. Pencils" not in text` |
| `test_streaming_sync_fallback_model_success` | Primary model raises `RuntimeError` | Fallback model invoked, yields `["fallback success"]` |
| `test_streaming_async_fallback_model_success` | Primary model raises `RuntimeError` in async stream | Fallback model invoked, yields `["async fallback success"]` |
