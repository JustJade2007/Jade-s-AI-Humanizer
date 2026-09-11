# Remediation Strategy & Technical Specification: `src/humanizer/client.py`

**Component**: Client Core (`src/humanizer/client.py`)  
**Author**: `explorer_m1_it2_1`  
**Target Milestone**: Milestone 1 Iteration 2 (Core Engine & Guardrails Remediation)  
**Date**: 2026-09-10T09:30:00Z  

---

## 1. Executive Summary

Empirical adversarial testing and peer review in Milestone 1 Iteration 1 revealed three critical defects localized to `src/humanizer/client.py`:
1. **Code block restoration order inverted**: `_restore_code_blocks` was executed before `replace_banned_buzzwords` and `sanitize_and_verify_grammar`, causing guardrails to mutate code comments, string literals, and code formatting inside markdown fences (violating Project Requirement R3).
2. **Streaming code block & buzzword fragmentation leaks**: `humanize_stream` and `humanize_stream_sync` performed per-chunk restoration and regex substitution without buffering. When LLMs split `⟦CODE_FENCE_0⟧` or multi-word buzzwords (e.g. `In summary`) across token chunk boundaries, raw placeholders leaked into the stream, code blocks were lost, and banned buzzwords escaped replacement.
3. **Missing client attributes**: `Humanizer` failed to assign `self.model`, `self.fallback_model`, `self.api_key`, and `self.mock_mode`, causing `AttributeError` failures across the E2E test suite.

This document specifies the exact architecture, algorithms, and before/after code snippets for remediating `src/humanizer/client.py`.

---

## 2. Issue 1: Code Block Restoration Order in `_post_process`

### 2.1 Problem Analysis
In `src/humanizer/client.py:84-101`:
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
The comment claimed to restore code blocks so guardrails wouldn't rewrite code, but doing so restored the code *directly into the string passed to `replace_banned_buzzwords` and `sanitize_and_verify_grammar`*.
Consequently:
- Comments like `# We must delve into the algorithm` were changed to `# We must explore the algorithm`.
- Strings like `message = 'This is a tapestry of colors'` were corrupted to `message = 'This is a blend of colors'`.
- Code syntax like `items = [1 , 2 , 3]` had whitespace collapsed to `items = [1, 2, 3]`.

### 2.2 Remediation Design
1. Retain the code fence placeholders (`⟦CODE_FENCE_0⟧`) in `raw_output` during all prose transformations.
2. Run `replace_banned_buzzwords` on the text with placeholders in place. The placeholder tokens use mathematical white square brackets `⟦` (`\u27e6`) and `⟧` (`\u27e7`), which do not match any buzzword pattern.
3. Filter `original_text` to strip code blocks before calculating `original_buzzwords` so buzzwords inside user code comments are not mistakenly reported in `buzzwords_replaced`.
4. Run `sanitize_and_verify_grammar` on the prose with placeholders in place. Because `backtick_count` checks triple backticks (which are currently masked as placeholders), the code fences are not disturbed.
5. **Absolute Last Transformation Step**: Call `self._restore_code_blocks(repaired_prose, fences)` on the repaired prose.
6. Calculate readability scores on the final text (which internally strips markdown code fences via `_strip_markdown_and_code`).

### 2.3 Before vs. After Code Snippet

#### Before (`src/humanizer/client.py:72-118`):
```python
    def _post_process(
        self,
        raw_output: str,
        original_text: str,
        mode: str,
        tone: str,
        reading_level: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        fences: list[str],
    ) -> HumanizeResult:
        # Restore code blocks first so guardrails don't rewrite code
        restored = self._restore_code_blocks(raw_output, fences)

        # 1. 0-tolerance banned AI buzzwords audit and replacement
        clean_text, buzzwords_replaced = replace_banned_buzzwords(restored)

        # Also capture buzzwords present in original_text that were eliminated during humanization
        original_buzzwords = audit_vocabulary(original_text)
        all_buzzwords = list(buzzwords_replaced)
        for bw in original_buzzwords:
            if not re.search(r"\b" + re.escape(bw) + r"\b", clean_text, re.IGNORECASE):
                if bw not in all_buzzwords:
                    all_buzzwords.append(bw)

        # 2. Automated syntax & grammar verification
        grammar_res = sanitize_and_verify_grammar(clean_text)
        final_text = grammar_res.repaired_text

        # 3. Readability score calculation
        readability = calculate_readability(final_text)

        return HumanizeResult(...)
```

#### After (`src/humanizer/client.py:72-118`):
```python
    def _post_process(
        self,
        raw_output: str,
        original_text: str,
        mode: str,
        tone: str,
        reading_level: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        fences: list[str],
    ) -> HumanizeResult:
        # 1. 0-tolerance banned AI buzzwords audit and replacement on prose
        # Fenced code block placeholders ⟦CODE_FENCE_X⟧ remain masked and untouched
        clean_text, buzzwords_replaced = replace_banned_buzzwords(raw_output)

        # Capture buzzwords eliminated from original_text prose (excluding code blocks)
        original_prose = re.sub(r"```[\s\S]*?```", " ", original_text) if fences else original_text
        original_buzzwords = audit_vocabulary(original_prose)
        all_buzzwords = list(buzzwords_replaced)
        for bw in original_buzzwords:
            if not re.search(r"\b" + re.escape(bw) + r"\b", clean_text, re.IGNORECASE):
                if bw not in all_buzzwords:
                    all_buzzwords.append(bw)

        # 2. Automated syntax & grammar verification on prose only
        grammar_res = sanitize_and_verify_grammar(clean_text)
        repaired_prose = grammar_res.repaired_text

        # 3. RESTORE CODE BLOCKS AS THE ABSOLUTE LAST STEP OF TEXT TRANSFORMATION
        # Code comments, string literals, and syntax formatting inside fenced blocks
        # are NEVER altered by guardrails or grammar sanitizers
        final_text = self._restore_code_blocks(repaired_prose, fences)

        # 4. Readability score calculation (calculate_readability strips code blocks internally)
        readability = calculate_readability(final_text)

        return HumanizeResult(
            text=final_text,
            original_text=original_text,
            mode=mode,
            tone=tone,
            reading_level=reading_level,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            buzzwords_replaced=all_buzzwords,
            flesch_reading_ease=readability["flesch_reading_ease"],
            flesch_kincaid_grade=readability["flesch_kincaid_grade"],
            grammar_repaired=not grammar_res.is_valid,
        )
```

Also harden `_restore_code_blocks` to safely use string replacement and regex lambdas (avoiding backslash escaping traps like `\1` or `\n` in code):
```python
    def _restore_code_blocks(self, text: str, fences: list[str]) -> str:
        """Restore protected code blocks bit-for-bit."""
        restored = text
        for idx, fence in enumerate(fences):
            target = f"⟦CODE_FENCE_{idx}⟧"
            if target in restored:
                restored = restored.replace(target, fence)
            else:
                # Tolerant fallback if LLM introduced spaces inside the brackets
                pattern = rf"⟦\s*CODE_FENCE_{idx}\s*⟧"
                restored = re.sub(pattern, lambda _: fence, restored)
        return restored
```

---

## 3. Issue 2: Streaming Chunk Accumulator for Code Blocks & Buzzwords

### 3.1 Problem Analysis
In `src/humanizer/client.py:229-234`:
```python
async for chunk in self.generator.generate_stream_async(payload_text, system_instruction):
    restored_chunk = self._restore_code_blocks(chunk, fences)
    clean_chunk, _ = replace_banned_buzzwords(restored_chunk)
    yield clean_chunk
```
When an LLM streams tokens:
- **Placeholder fragmentation**: A placeholder like `⟦CODE_FENCE_0⟧` is frequently split into sub-tokens: `["Before code. ", "⟦CODE_", "FENCE_0⟧ ", "After code."]`. Because `_restore_code_blocks` was called on each individual chunk, neither chunk contained the full key `⟦CODE_FENCE_0⟧`. The placeholder leaked as literal text, and `fences[0]` was never emitted!
- **Buzzword chunk boundary leak**: A multi-word phrase like `In summary,` split into `["In ", "summary, we must examine this."]` bypassed `replace_banned_buzzwords` because `"In "` alone didn't match and `"summary, ..."` alone didn't match.

### 3.2 Remediation Design: `StreamChunkAccumulator`
A dedicated accumulator buffer class (`StreamChunkAccumulator`) coordinates the streaming lifecycle:

1. **State**:
   - `self.fences: list[str]`: User's original fenced code blocks.
   - `self.buffer: str`: Incoming chunk accumulator buffer.

2. **Placeholder Preservation**:
   - Detect complete placeholders `⟦\s*CODE_FENCE_(\d+)\s*⟧`:
     - Flush and sanitize any prose preceding `m.start()`.
     - Emit the original code block `self.fences[idx]` **directly** without passing it through `replace_banned_buzzwords`.
     - Slice `self.buffer` to `m.end()` and continue.
   - Detect partial placeholders: If `⟦` is present in `self.buffer` without a closing `⟧`, and the tail is `< 30` chars without newlines, **retain the tail in the buffer** and only consider text before `⟦` for emission.

3. **Buzzword Boundary Protection**:
   - Multi-word phrases in `guardrails.py` start with specific words (`BUZZWORD_STARTERS`: `"in"`, `"delve"`, `"it"`, `"shed"`, `"serves"`, `"tapestry"`, etc.).
   - If candidate prose text contains a sentence boundary (`[.!?]\s+` or `\n+`), all text up to the boundary is 100% immune to crossing phrases. It is sanitized via `replace_banned_buzzwords` and yielded immediately.
   - If no sentence boundary exists, evaluate word boundaries from right to left: find the last whitespace where the preceding word is NOT in `BUZZWORD_STARTERS` or `BUZZWORD_INTERNAL_WORDS`. Sanitize and emit up to that whitespace, retaining the remainder.
   - If an ongoing potential buzzword phrase is detected, hold it in `self.buffer` until more tokens arrive or the stream ends.

4. **EOF Flush**:
   - At stream completion (`flush()`), resolve any remaining placeholders, sanitize all remaining prose via `replace_banned_buzzwords`, and yield the final chunks.

### 3.3 Implementation of `StreamChunkAccumulator`
```python
class StreamChunkAccumulator:
    """Accumulates and safely emits streaming chunks without leaking placeholders or buzzwords."""

    # Words that can begin a multi-word banned AI cliché or transition phrase
    BUZZWORD_STARTERS = {
        "serves", "serve",
        "it",
        "shed", "sheds",
        "paradigm",
        "game",
        "by",
        "delve", "delves", "delved", "delving",
        "tapestry", "tapestries",
        "in",
        "to",
        "testament", "testaments",
        "symphony", "symphonies",
        "plethora",
        "myriad",
        "realm", "realms",
        "interplay",
        "beacon", "beacons",
    }

    # All internal vocabulary words that can appear inside multi-word banned phrases
    BUZZWORD_INTERNAL_WORDS = {
        "as", "a", "testament", "testaments", "to", "beacon", "beacons", "of",
        "reminder", "is", "worth", "noting", "that", "important", "remember",
        "light", "on", "shift", "changer", "and", "large", "into", "summary",
        "conclusion", "sum", "up",
    }

    PLACEHOLDER_REGEX = re.compile(r"⟦\s*CODE_FENCE_(\d+)\s*⟧")
    SENTENCE_BOUNDARY_REGEX = re.compile(r"([.!?]\s+|\n+)")

    def __init__(self, fences: list[str]) -> None:
        self.fences = fences
        self.buffer = ""

    def feed(self, chunk: str) -> Iterator[str]:
        """Feed an incoming chunk and yield any safely sanitized and restored output."""
        if not chunk:
            return

        self.buffer += chunk

        while True:
            # 1. Check for complete code fence placeholder in buffer
            placeholder_match = self.PLACEHOLDER_REGEX.search(self.buffer)
            if placeholder_match:
                prefix = self.buffer[:placeholder_match.start()]
                if prefix:
                    clean_prefix, _ = replace_banned_buzzwords(prefix)
                    if clean_prefix:
                        yield clean_prefix

                idx = int(placeholder_match.group(1))
                restored_fence = self.fences[idx] if idx < len(self.fences) else placeholder_match.group(0)
                yield restored_fence

                self.buffer = self.buffer[placeholder_match.end():]
                continue

            # 2. Check for partial code fence placeholder at end of buffer
            partial_idx = self.buffer.rfind("⟦")
            candidate_text = self.buffer
            reserved_tail = ""
            if partial_idx != -1:
                tail = self.buffer[partial_idx:]
                if "\n" not in tail and len(tail) < 30 and "⟧" not in tail:
                    candidate_text = self.buffer[:partial_idx]
                    reserved_tail = tail

            if not candidate_text:
                break

            # 3. Check for safe prose emission in candidate_text
            # Look for sentence boundary
            sentence_matches = list(self.SENTENCE_BOUNDARY_REGEX.finditer(candidate_text))
            if sentence_matches:
                last_match = sentence_matches[-1]
                safe_slice = candidate_text[:last_match.end()]
                remainder = candidate_text[last_match.end():]

                clean_slice, _ = replace_banned_buzzwords(safe_slice)
                if clean_slice:
                    yield clean_slice

                self.buffer = remainder + reserved_tail
                continue

            # Check word boundaries for safe split points
            emitted = False
            space_indices = [m.start() for m in re.finditer(r"\s+", candidate_text)]
            for s_idx in reversed(space_indices):
                pre_slice = candidate_text[:s_idx]
                post_slice = candidate_text[s_idx:]

                words = re.findall(r"[a-zA-Z]+", pre_slice)
                if not words:
                    continue
                last_word = words[-1].lower()

                # If last word could begin or continue a multi-word phrase, hold in buffer
                if last_word in self.BUZZWORD_STARTERS or last_word in self.BUZZWORD_INTERNAL_WORDS:
                    continue

                clean_slice, _ = replace_banned_buzzwords(pre_slice)
                if clean_slice:
                    yield clean_slice

                self.buffer = post_slice + reserved_tail
                emitted = True
                break

            if not emitted:
                break

    def flush(self) -> Iterator[str]:
        """Flush any remaining text in buffer on stream completion."""
        if not self.buffer:
            return

        while True:
            m = self.PLACEHOLDER_REGEX.search(self.buffer)
            if not m:
                break
            prefix = self.buffer[:m.start()]
            if prefix:
                clean_prefix, _ = replace_banned_buzzwords(prefix)
                if clean_prefix:
                    yield clean_prefix

            idx = int(m.group(1))
            restored_fence = self.fences[idx] if idx < len(self.fences) else m.group(0)
            yield restored_fence

            self.buffer = self.buffer[m.end():]

        if self.buffer:
            clean_tail, _ = replace_banned_buzzwords(self.buffer)
            if clean_tail:
                yield clean_tail
            self.buffer = ""
```

### 3.4 Integration in `humanize_stream` and `humanize_stream_sync`
```python
    async def humanize_stream(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> AsyncIterator[str]:
        """Asynchronously stream humanized text chunks."""
        if not text or not text.strip():
            yield text
            return

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        accumulator = StreamChunkAccumulator(fences=fences)
        async for chunk in self.generator.generate_stream_async(payload_text, system_instruction):
            for clean_chunk in accumulator.feed(chunk):
                yield clean_chunk
        for remaining_chunk in accumulator.flush():
            yield remaining_chunk

    def humanize_stream_sync(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> Iterator[str]:
        """Synchronously stream humanized text chunks."""
        if not text or not text.strip():
            yield text
            return

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        accumulator = StreamChunkAccumulator(fences=fences)
        for chunk in self.generator.generate_stream_sync(payload_text, system_instruction):
            for clean_chunk in accumulator.feed(chunk):
                yield clean_chunk
        for remaining_chunk in accumulator.flush():
            yield remaining_chunk
```

---

## 4. Issue 3: Missing Client Attributes on `Humanizer`

### 4.1 Problem Analysis
In `src/humanizer/client.py:22-42`:
```python
class Humanizer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.0-flash-lite",
        mock_mode: bool = False,
    ) -> None:
        self.generator = GeminiGenerator(...)
```
Parameters were passed to `GeminiGenerator`, but not assigned to `self`.
Tests inspecting `h.model`, `h.fallback_model`, `h.api_key`, and `h.mock_mode` crashed with `AttributeError`.

### 4.2 Remediation Design
Update `Humanizer.__init__` to assign all four attributes directly:
```python
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.0-flash-lite",
        mock_mode: bool = False,
    ) -> None:
        """Initialize the Humanizer client.

        Args:
            api_key: Optional Gemini API key. Defaults to GEMINI_API_KEY env var.
            model: Primary Flash Lite model. Defaults to 'gemini-2.5-flash-lite'.
            fallback_model: Secondary fallback model. Defaults to 'gemini-2.0-flash-lite'.
            mock_mode: When True, runs deterministic offline engine without network calls.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.fallback_model = fallback_model
        self.generator = GeminiGenerator(
            api_key=api_key,
            model=model,
            fallback_model=fallback_model,
            mock_mode=mock_mode,
        )
        self.mock_mode = self.generator.mock_mode
```
Note that `self.mock_mode` is set to `self.generator.mock_mode`, accurately reflecting offline simulation when `GEMINI_API_KEY` is not present or when `google-genai` is not installed.

---

## 5. Complete Proposed Replacement for `src/humanizer/client.py`

```python
"""Core Humanizer client interface providing sync, async, and streaming methods."""

from __future__ import annotations

import os
import re
from typing import AsyncIterator, Iterator, Literal, Optional

from humanizer.engine.generator import GeminiGenerator
from humanizer.engine.guardrails import (
    audit_vocabulary,
    replace_banned_buzzwords,
    sanitize_and_verify_grammar,
)
from humanizer.engine.prompt import get_budget_prompt, get_deep_prompt
from humanizer.engine.readability import calculate_readability
from humanizer.models import HumanizeResult, ModePreset, ReadingLevelPreset, TonePreset


class StreamChunkAccumulator:
    """Accumulates and safely emits streaming chunks without leaking placeholders or buzzwords."""

    # Words that can begin a multi-word banned AI cliché or transition phrase
    BUZZWORD_STARTERS = {
        "serves", "serve",
        "it",
        "shed", "sheds",
        "paradigm",
        "game",
        "by",
        "delve", "delves", "delved", "delving",
        "tapestry", "tapestries",
        "in",
        "to",
        "testament", "testaments",
        "symphony", "symphonies",
        "plethora",
        "myriad",
        "realm", "realms",
        "interplay",
        "beacon", "beacons",
    }

    # All internal vocabulary words that can appear inside multi-word banned phrases
    BUZZWORD_INTERNAL_WORDS = {
        "as", "a", "testament", "testaments", "to", "beacon", "beacons", "of",
        "reminder", "is", "worth", "noting", "that", "important", "remember",
        "light", "on", "shift", "changer", "and", "large", "into", "summary",
        "conclusion", "sum", "up",
    }

    PLACEHOLDER_REGEX = re.compile(r"⟦\s*CODE_FENCE_(\d+)\s*⟧")
    SENTENCE_BOUNDARY_REGEX = re.compile(r"([.!?]\s+|\n+)")

    def __init__(self, fences: list[str]) -> None:
        self.fences = fences
        self.buffer = ""

    def feed(self, chunk: str) -> Iterator[str]:
        """Feed an incoming chunk and yield any safely sanitized and restored output."""
        if not chunk:
            return

        self.buffer += chunk

        while True:
            # 1. Check for complete code fence placeholder in buffer
            placeholder_match = self.PLACEHOLDER_REGEX.search(self.buffer)
            if placeholder_match:
                prefix = self.buffer[:placeholder_match.start()]
                if prefix:
                    clean_prefix, _ = replace_banned_buzzwords(prefix)
                    if clean_prefix:
                        yield clean_prefix

                idx = int(placeholder_match.group(1))
                restored_fence = self.fences[idx] if idx < len(self.fences) else placeholder_match.group(0)
                yield restored_fence

                self.buffer = self.buffer[placeholder_match.end():]
                continue

            # 2. Check for partial code fence placeholder at end of buffer
            partial_idx = self.buffer.rfind("⟦")
            candidate_text = self.buffer
            reserved_tail = ""
            if partial_idx != -1:
                tail = self.buffer[partial_idx:]
                if "\n" not in tail and len(tail) < 30 and "⟧" not in tail:
                    candidate_text = self.buffer[:partial_idx]
                    reserved_tail = tail

            if not candidate_text:
                break

            # 3. Check for safe prose emission in candidate_text
            # Look for sentence boundary
            sentence_matches = list(self.SENTENCE_BOUNDARY_REGEX.finditer(candidate_text))
            if sentence_matches:
                last_match = sentence_matches[-1]
                safe_slice = candidate_text[:last_match.end()]
                remainder = candidate_text[last_match.end():]

                clean_slice, _ = replace_banned_buzzwords(safe_slice)
                if clean_slice:
                    yield clean_slice

                self.buffer = remainder + reserved_tail
                continue

            # Check word boundaries for safe split points
            emitted = False
            space_indices = [m.start() for m in re.finditer(r"\s+", candidate_text)]
            for s_idx in reversed(space_indices):
                pre_slice = candidate_text[:s_idx]
                post_slice = candidate_text[s_idx:]

                words = re.findall(r"[a-zA-Z]+", pre_slice)
                if not words:
                    continue
                last_word = words[-1].lower()

                # If last word could begin or continue a multi-word phrase, hold in buffer
                if last_word in self.BUZZWORD_STARTERS or last_word in self.BUZZWORD_INTERNAL_WORDS:
                    continue

                clean_slice, _ = replace_banned_buzzwords(pre_slice)
                if clean_slice:
                    yield clean_slice

                self.buffer = post_slice + reserved_tail
                emitted = True
                break

            if not emitted:
                break

    def flush(self) -> Iterator[str]:
        """Flush any remaining text in buffer on stream completion."""
        if not self.buffer:
            return

        while True:
            m = self.PLACEHOLDER_REGEX.search(self.buffer)
            if not m:
                break
            prefix = self.buffer[:m.start()]
            if prefix:
                clean_prefix, _ = replace_banned_buzzwords(prefix)
                if clean_prefix:
                    yield clean_prefix

            idx = int(m.group(1))
            restored_fence = self.fences[idx] if idx < len(self.fences) else m.group(0)
            yield restored_fence

            self.buffer = self.buffer[m.end():]

        if self.buffer:
            clean_tail, _ = replace_banned_buzzwords(self.buffer)
            if clean_tail:
                yield clean_tail
            self.buffer = ""


class Humanizer:
    """Core text humanizer client conforming to PROJECT.md § Interface Contracts."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        fallback_model: str = "gemini-2.0-flash-lite",
        mock_mode: bool = False,
    ) -> None:
        """Initialize the Humanizer client.

        Args:
            api_key: Optional Gemini API key. Defaults to GEMINI_API_KEY env var.
            model: Primary Flash Lite model. Defaults to 'gemini-2.5-flash-lite'.
            fallback_model: Secondary fallback model. Defaults to 'gemini-2.0-flash-lite'.
            mock_mode: When True, runs deterministic offline engine without network calls.
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        self.fallback_model = fallback_model
        self.generator = GeminiGenerator(
            api_key=api_key,
            model=model,
            fallback_model=fallback_model,
            mock_mode=mock_mode,
        )
        self.mock_mode = self.generator.mock_mode

    def _prepare_prompt(
        self,
        mode: Literal["budget", "deep"],
        tone: Literal["neutral", "casual", "academic", "professional"],
        reading_level: Literal["middle_school", "high_school", "college", "general"],
    ) -> str:
        if mode == "deep":
            return get_deep_prompt(tone=tone, reading_level=reading_level)
        return get_budget_prompt(tone=tone, reading_level=reading_level)

    def _protect_code_blocks(self, text: str) -> tuple[str, list[str]]:
        """Safeguard fenced code blocks from modification."""
        fences: list[str] = []

        def _repl(m: re.Match[str]) -> str:
            fences.append(m.group(0))
            return f"⟦CODE_FENCE_{len(fences)-1}⟧"

        protected = re.sub(r"```[\s\S]*?```", _repl, text)
        return protected, fences

    def _restore_code_blocks(self, text: str, fences: list[str]) -> str:
        """Restore protected code blocks bit-for-bit."""
        restored = text
        for idx, fence in enumerate(fences):
            target = f"⟦CODE_FENCE_{idx}⟧"
            if target in restored:
                restored = restored.replace(target, fence)
            else:
                pattern = rf"⟦\s*CODE_FENCE_{idx}\s*⟧"
                restored = re.sub(pattern, lambda _: fence, restored)
        return restored

    def _post_process(
        self,
        raw_output: str,
        original_text: str,
        mode: str,
        tone: str,
        reading_level: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        fences: list[str],
    ) -> HumanizeResult:
        # 1. 0-tolerance banned AI buzzwords audit and replacement on prose
        # Fenced code block placeholders ⟦CODE_FENCE_X⟧ remain masked and untouched
        clean_text, buzzwords_replaced = replace_banned_buzzwords(raw_output)

        # Capture buzzwords eliminated from original_text prose (excluding code blocks)
        original_prose = re.sub(r"```[\s\S]*?```", " ", original_text) if fences else original_text
        original_buzzwords = audit_vocabulary(original_prose)
        all_buzzwords = list(buzzwords_replaced)
        for bw in original_buzzwords:
            if not re.search(r"\b" + re.escape(bw) + r"\b", clean_text, re.IGNORECASE):
                if bw not in all_buzzwords:
                    all_buzzwords.append(bw)

        # 2. Automated syntax & grammar verification on prose only
        grammar_res = sanitize_and_verify_grammar(clean_text)
        repaired_prose = grammar_res.repaired_text

        # 3. RESTORE CODE BLOCKS AS THE ABSOLUTE LAST STEP OF TEXT TRANSFORMATION
        # Code comments, string literals, and syntax formatting inside fenced blocks
        # are NEVER altered by guardrails or grammar sanitizers
        final_text = self._restore_code_blocks(repaired_prose, fences)

        # 4. Readability score calculation (calculate_readability strips code blocks internally)
        readability = calculate_readability(final_text)

        return HumanizeResult(
            text=final_text,
            original_text=original_text,
            mode=mode,
            tone=tone,
            reading_level=reading_level,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            buzzwords_replaced=all_buzzwords,
            flesch_reading_ease=readability["flesch_reading_ease"],
            flesch_kincaid_grade=readability["flesch_kincaid_grade"],
            grammar_repaired=not grammar_res.is_valid,
        )

    def humanize(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> HumanizeResult:
        """Synchronously humanize text with quality guardrails and readability evaluation."""
        if not text or not text.strip():
            return HumanizeResult(
                text=text,
                original_text=text,
                mode=mode,
                tone=tone,
                reading_level=reading_level,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                buzzwords_replaced=[],
                flesch_reading_ease=100.0,
                flesch_kincaid_grade=0.0,
                grammar_repaired=False,
            )

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        raw_output, usage = self.generator.generate_sync(payload_text, system_instruction)

        return self._post_process(
            raw_output=raw_output,
            original_text=text,
            mode=mode,
            tone=tone,
            reading_level=reading_level,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            fences=fences,
        )

    async def humanize_async(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> HumanizeResult:
        """Asynchronously humanize text with quality guardrails and readability evaluation."""
        if not text or not text.strip():
            return HumanizeResult(
                text=text,
                original_text=text,
                mode=mode,
                tone=tone,
                reading_level=reading_level,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                buzzwords_replaced=[],
                flesch_reading_ease=100.0,
                flesch_kincaid_grade=0.0,
                grammar_repaired=False,
            )

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        raw_output, usage = await self.generator.generate_async(payload_text, system_instruction)

        return self._post_process(
            raw_output=raw_output,
            original_text=text,
            mode=mode,
            tone=tone,
            reading_level=reading_level,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            fences=fences,
        )

    async def humanize_stream(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> AsyncIterator[str]:
        """Asynchronously stream humanized text chunks."""
        if not text or not text.strip():
            yield text
            return

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        accumulator = StreamChunkAccumulator(fences=fences)
        async for chunk in self.generator.generate_stream_async(payload_text, system_instruction):
            for clean_chunk in accumulator.feed(chunk):
                yield clean_chunk
        for remaining_chunk in accumulator.flush():
            yield remaining_chunk

    def humanize_stream_sync(
        self,
        text: str,
        mode: Literal["budget", "deep"] = "budget",
        tone: Literal["neutral", "casual", "academic", "professional"] = "neutral",
        reading_level: Literal["middle_school", "high_school", "college", "general"] = "general",
        preserve_markdown: bool = True,
    ) -> Iterator[str]:
        """Synchronously stream humanized text chunks."""
        if not text or not text.strip():
            yield text
            return

        fences: list[str] = []
        payload_text = text
        if preserve_markdown:
            payload_text, fences = self._protect_code_blocks(text)

        system_instruction = self._prepare_prompt(mode, tone, reading_level)
        accumulator = StreamChunkAccumulator(fences=fences)
        for chunk in self.generator.generate_stream_sync(payload_text, system_instruction):
            for clean_chunk in accumulator.feed(chunk):
                yield clean_chunk
        for remaining_chunk in accumulator.flush():
            yield remaining_chunk
```

---

## 6. Verification Plan

| Test ID | Test Name | Expected Result with Remediation |
|---------|-----------|----------------------------------|
| ADV-E1 | `test_code_block_guardrail_corruption_buzzwords_in_strings` | `# We must delve into the algorithm` and `message = 'This is a tapestry of colors'` in code block remain 100% byte-for-byte unmodified. PASS |
| ADV-E2 | `test_code_block_guardrail_corruption_grammar_sanitizer` | `items = [1 , 2 , 3]` inside code block remains unmodified. PASS |
| ADV-E3 | `test_streaming_code_block_fragmentation_leak` | Split placeholder `⟦CODE_` + `FENCE_0⟧` reassembles, no `⟦CODE_` in output, code block `print('secret_code')` accurately reconstructed. PASS |
| ADV-E4 | `test_streaming_buzzword_chunk_boundary_leak` | Split phrase `In ` + `summary, ...` buffered and replaced with `overall, ...`, 0 buzzword leaks. PASS |
| E2E-F1.4 | `test_f1_04_humanizer_default_parameters` | `h.model` and `h.mock_mode` exist on `h`. PASS |
| E2E-F2.1 | `test_f2_01_api_key_from_constructor` | `h.api_key` matches constructor parameter. PASS |
| E2E-F2.2 | `test_f2_02_api_key_from_env` | `h.api_key` matches `GEMINI_API_KEY` env var. PASS |
| E2E-F2.B4 | `test_f2_b04_fallback_model_selection` | `h.fallback_model` matches parameter. PASS |
| E2E-F3.C3 | `test_f3_c03_streaming_with_markdown_preservation` | Streaming markdown doc with python code block reconstructed bit-for-bit. PASS |
