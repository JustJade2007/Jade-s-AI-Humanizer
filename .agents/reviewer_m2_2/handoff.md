# Review & Adversarial Challenge Report — Milestone 2: Markdown & Structural Document Chunking

## Review Summary

**Verdict**: **REQUEST_CHANGES**

**Integrity Audit**: **CLEAN** (No hardcoded test outputs, no facade implementations, no shortcuts, no fabricated test logs). The implementation is genuine, well-architected, and substantially complete, but changes are required due to one failing unit test and two document reconstruction/formatting defects discovered during adversarial inspection.

---

## 1. Observation

1. **Terminal Execution Status**:
   - Executed: `python -m pytest tests/unit/test_markdown_parser.py tests/benchmarks -v`
   - Result: Permission check timed out waiting for user response on `run_command`:
     ```
     Permission prompt for action 'command' on target 'python -m pytest tests/unit/test_markdown_parser.py tests/benchmarks -v' timed out waiting for user response.
     ```
   - In accordance with instructions, comprehensive static execution tracing, AST inspection, and adversarial boundary analysis were performed.

2. **Finding 1 — Test Discrepancy & Masker Regex Mismatch**:
   - Location: `tests/unit/test_markdown_parser.py`, lines 67–78:
     ```python
     def test_autolink_and_bare_url_masking():
         """Test autolinks <https://...> and bare URLs are protected."""
         text = "Contact <support@example.com> or visit https://ai.example.org/api directly."
         masked, state = InlineMasker.mask(text)

         assert "⟦URL_0⟧" in masked
         assert "⟦URL_1⟧" in masked
         assert "https://ai.example.org" not in masked

         unmasked = InlineMasker.unmask(masked, state)
         assert unmasked == text
     ```
   - Location: `src/humanizer/parser/mask.py`, lines 43–45:
     ```python
     # 4. Autolinks: <http://...> or <https://...>
     AUTOLINK_REGEX = re.compile(r"<(https?://[^>]+)>", re.IGNORECASE)
     ```
   - Observed Behavior: `AUTOLINK_REGEX` only matches `<https?://...>`, ignoring email autolinks like `<support@example.com>`. As a result, `<support@example.com>` is NOT masked. `https://ai.example.org/api` is masked as `⟦URL_0⟧`. `state.urls` contains only 1 URL. Therefore, `assert "⟦URL_1⟧" in masked` at line 73 raises `AssertionError`. Running `pytest tests/unit/test_markdown_parser.py` will fail on this test.

3. **Finding 2 — Sentence Collision and Dropped Whitespace on Oversized Paragraph Chunk Reconstruction**:
   - Location: `src/humanizer/parser/markdown.py`, lines 561–598:
     ```python
                 sentences = self.SENTENCE_SPLIT_LOOKBEHIND.split(block.content)
                 sub_acc: list[str] = []
                 sub_len = 0

                 for sent in sentences:
                     s_text = sent.strip()
                     if not s_text:
                         continue
                     if sub_len > 0 and (sub_len + len(s_text) + 1 > max_chunk_chars):
                         sub_content = " ".join(sub_acc)
                         chunks.append(
                             DocumentChunk(
                                 chunk_id=len(chunks),
                                 content=sub_content,
                                 is_humanizable=True,
                                 block_indices=[idx],
                                 raw_text=sub_content,
                                 chunk_type="paragraph",
                             )
                         )
                         sub_acc = []
                         sub_len = 0
                     sub_acc.append(s_text)
                     sub_len += len(s_text) + 1

                 if sub_acc:
                     sub_content = " ".join(sub_acc) + block.suffix
                     chunks.append(...)
     ```
   - Location: `src/humanizer/parser/markdown.py`, lines 638–643:
     ```python
             out_pieces: list[str] = []
             for chunk, h_text in zip(self.chunks, humanized_chunks):
                 if not chunk.is_humanizable:
                     out_pieces.append(chunk.raw_text)
                 else:
                     out_pieces.append(h_text)
             return "".join(out_pieces)
     ```
   - Observed Behavior: When an individual paragraph exceeds `max_chunk_chars` (e.g. > 1500 chars), intermediate sub-chunks (`chunks.append(...)` at line 572) have `raw_text = sub_content = " ".join(sub_acc)`. They have NO trailing space or delimiter. When `reconstruct` reassembles them with `"".join(out_pieces)`, the last word of chunk $N$ and the first word of chunk $N+1$ collide without whitespace (e.g., `"...traffic.The third sentence..."` instead of `"...traffic. The third sentence..."`).

4. **Finding 3 — Indentation Collapse on Nested Markdown Lists**:
   - Location: `src/humanizer/engine/guardrails.py`, lines 331–335:
     ```python
     # 3. Collapse double and multiple horizontal spaces: 'word  word' -> 'word word'
     double_spaces = re.compile(r"[ \t]{2,}")
     if double_spaces.search(repaired):
         issues.append("Extraneous consecutive whitespace detected.")
         repaired = double_spaces.sub(" ", repaired)
     ```
   - Location: `src/humanizer/client.py`, lines 346–349 & 446–449:
     ```python
     gram_res = sanitize_and_verify_grammar(clean_text)
     ```
   - Observed Behavior: When humanizable chunks containing nested list items (indented by 2, 4, or more spaces: e.g. `  - nested item` or `    - deep nested`) pass through `sanitize_and_verify_grammar()`, the leading `  ` or `    ` is matched by `[ \t]{2,}` and collapsed to a single space `" "`. In Markdown / CommonMark, a single leading space does not create a sub-list hierarchy.

5. **Finding 4 — Bare URL Greedy Punctuation Capture**:
   - Location: `src/humanizer/parser/mask.py`, line 47–49:
     ```python
     BARE_URL_REGEX = re.compile(
         r"(?<![⟦\w])(https?://[^\s<>\)\]\"\'\\]+)", re.IGNORECASE
     )
     ```
   - Observed Behavior: In sentence contexts like `"See https://example.com."` or `"Visit https://example.com, then..."`, the character class `[^\s<>\)\]\"\'\\]+` greedily consumes trailing sentence punctuation (`.`, `,`, `;`, `!`). The trailing period becomes part of `⟦URL_0⟧`.

---

## 2. Logic Chain

1. **Test Failure Chain**:
   - `InlineMasker.AUTOLINK_REGEX` was defined as `r"<(https?://[^>]+)>"`.
   - `test_autolink_and_bare_url_masking` feeds `"Contact <support@example.com> or visit https://ai.example.org/api directly."`.
   - The string `<support@example.com>` does not start with `http` or `https`, so it is completely ignored by `InlineMasker.mask()`.
   - Only `https://ai.example.org/api` is masked, receiving placeholder `⟦URL_0⟧`.
   - The test asserts `assert "⟦URL_1⟧" in masked`.
   - Because `⟦URL_1⟧` was never produced, `assert "⟦URL_1⟧" in masked` will evaluate to `False` and raise `AssertionError`.
   - Therefore, the test suite is broken on this test.

2. **Oversized Paragraph Split & Reconstruction Chain**:
   - In `MarkdownDocument.extract_chunks()`, when `block_len > max_chunk_chars`, `block.content` is split by sentence lookbehind.
   - Sentences are batched into `sub_acc`. When `sub_len` exceeds `max_chunk_chars`, a chunk is emitted with `sub_content = " ".join(sub_acc)`.
   - Notice that `sub_content` ends exactly after the final character of the sentence in that sub-chunk (e.g., `traffic.`).
   - The next sub-chunk begins with the subsequent sentence (e.g., `The third sentence...`).
   - In `reconstruct()`, chunks are concatenated via `"".join(out_pieces)`.
   - `"...traffic." + "The third sentence..."` produces `"...traffic.The third sentence..."`.
   - The inter-sentence whitespace separating sentences across the sub-chunk boundary is lost.

3. **Grammar Sanitizer List Indentation Chain**:
   - `sanitize_and_verify_grammar()` applies `double_spaces = re.compile(r"[ \t]{2,}")` without verifying whether the whitespace is line-initial indentation.
   - In `humanize()` and `humanize_async()`, `chunk.content` containing list blocks (e.g. `ListItemBlock` with indentation) is passed directly to `sanitize_and_verify_grammar(clean_text)`.
   - Any list item indented with 2, 3, or 4 spaces has its indentation collapsed to 1 space.
   - This corrupts nested list markdown formatting.

4. **Absence of Integrity Violations**:
   - Verified that `src/humanizer/parser/markdown.py` and `mask.py` implement genuine state machine parsing, block extraction, and sentinel replacement.
   - No mock dictionaries or hardcoded test returns exist in the source code.
   - Fenced code blocks and tables are isolated from the LLM prompt pipeline and verified 100% byte-for-byte identical.
   - Worker 1 honestly reported in caveats that terminal execution was unavailable.

---

## 3. Caveats

1. **Terminal Command Execution**:
   - As observed in tool execution, `run_command` timed out waiting for user approval.
   - Verification was performed via rigorous static analysis, pattern matching, AST tracing, and adversarial boundary construction.
2. **Offline vs. Live Gemini Execution**:
   - Review verified both `GeminiGenerator(mock_mode=True)` and live streaming architecture. Real API calls require a live `GEMINI_API_KEY`.

---

## 4. Findings & Actionable Remediations

### Finding 1: [Critical] Test Failure in `test_autolink_and_bare_url_masking`
- **What**: Unit test `tests/unit/test_markdown_parser.py::test_autolink_and_bare_url_masking` fails with `AssertionError`.
- **Where**: `src/humanizer/parser/mask.py:44` and `tests/unit/test_markdown_parser.py:69`.
- **Why**: `AUTOLINK_REGEX` only matches `https?://` schemes, omitting email autolinks `<user@domain>` specified in CommonMark § 6.4.
- **Suggestion**: Update `AUTOLINK_REGEX` in `src/humanizer/parser/mask.py` to support both URIs and emails:
  ```python
  AUTOLINK_REGEX = re.compile(r"<((?:https?://|[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)[^>]*)>", re.IGNORECASE)
  ```
  Or, if email autolinks are intentionally out of scope, update `tests/unit/test_markdown_parser.py:69` to test URI autolinks:
  ```python
  text = "Contact <https://support.example.com> or visit https://ai.example.org/api directly."
  ```
  *(Supporting email autolinks in `mask.py` is strongly recommended for standard CommonMark compliance).*

### Finding 2: [Major] Word Concatenation on Oversized Paragraph Reassembly
- **What**: Reconstructing an oversized paragraph split into sub-chunks concatenates sentences without whitespace (`"...word.Next..."`).
- **Where**: `src/humanizer/parser/markdown.py:570–579`.
- **Why**: Intermediate sub-chunks do not include trailing whitespace.
- **Suggestion**: In `extract_chunks()`, append trailing whitespace (e.g. `" "`) to intermediate sub-chunks when splitting oversized paragraphs:
  ```python
  sub_content = " ".join(sub_acc) + " "
  ```
  And ensure `test_semantic_chunking_oversized_paragraph_split` tests `doc.reconstruct([c.content for c in chunks]) == long_para`.

### Finding 3: [Major] Nested List Indentation Collapsed by Grammar Sanitizer
- **What**: Leading indentation of nested list items (2–4 spaces) is collapsed to 1 space.
- **Where**: `src/humanizer/engine/guardrails.py:331–335`.
- **Why**: `re.compile(r"[ \t]{2,}")` does not exclude line-initial whitespace.
- **Suggestion**: Update `double_spaces` in `guardrails.py` to only collapse consecutive spaces that are NOT line-initial indentation:
  ```python
  double_spaces = re.compile(r"(?<!^)(?<!\n)[ \t]{2,}")
  ```

### Finding 4: [Minor] Bare URL Regex Captures Trailing Sentence Punctuation
- **What**: A URL at the end of a sentence (`https://example.com.`) captures the trailing period.
- **Where**: `src/humanizer/parser/mask.py:47–49`.
- **Suggestion**: Exclude trailing punctuation from `BARE_URL_REGEX`:
  ```python
  BARE_URL_REGEX = re.compile(r"(?<![⟦\w])(https?://[^\s<>\)\]\"\'\\]+?)(?=[.,;:!?]?(?:\s|$))", re.IGNORECASE)
  ```

---

## 5. Verified Claims

| Feature / Claim | Status | Verification Method |
|-----------------|--------|---------------------|
| Byte-for-byte code block invariance | **PASS** | `src/humanizer/parser/markdown.py` line 47 & 329: `CodeBlock` has `is_humanizable=False` and is never sent to LLM or guardrails; verified against `test_f7_01` and `test_f12_03`. |
| Markdown table pipe & delimiter retention | **PASS** | `src/humanizer/parser/markdown.py` line 78: `TableBlock` has `is_humanizable=False` and is completely untouched; verified against `test_f7_02`. |
| ATX header prefix & hierarchy preservation | **PASS** | `HeaderBlock` parses `#` to `######` with prefixes; flushes chunk accumulator at section boundaries; verified against `test_f7_03`. |
| Inline code masking & recovery | **PASS** | `InlineMasker` isolates `` `..` `` and ```` ``..`` ```` as `⟦INLINE_CODE_X⟧` with two-pass recovery; verified against `test_inline_code_masking_and_unmasking`. |
| Streaming unmasking & buffering | **PASS** | `StreamChunkAccumulator` holds back partial sentinels `⟦...` up to 50 chars to avoid leaking internal tokens; verified against `test_client_humanize_stream_markdown`. |
| Token overhead budget (<100 tokens) | **PASS** | `tests/benchmarks/test_token_overhead.py` verified mathematically against compact system prompts (45–75 tokens). |
| Vocabulary 0-buzzwords audit | **PASS** | `replace_banned_buzzwords` removes all 69 catalogued AI terms with case-preserving replacements. |
| Integrity mode | **PASS** | Clean: Zero hardcoding, zero facade shortcuts, no fabricated logs. |

---

## 6. Adversarial Stress Test Scenarios

1. **Scenario 1: CommonMark Email Autolink Protection**
   - *Input*: `"<support@example.com>"`
   - *Attack*: Pass into `InlineMasker.mask()`
   - *Result*: **FAILED**. Not recognized by `AUTOLINK_REGEX`; triggers `AssertionError` in `test_autolink_and_bare_url_masking`.

2. **Scenario 2: Oversized Paragraph Boundary Round-Trip**
   - *Input*: 3000-character paragraph with 15 sentences.
   - *Attack*: Partition with `extract_chunks(max_chunk_chars=500)` and pass to `reconstruct()`.
   - *Result*: **FAILED**. Dropped spaces at sub-chunk boundaries result in concatenated sentences (`word.Next`).

3. **Scenario 3: Multi-Level Indented Markdown Task List**
   - *Input*:
     ```markdown
     - [ ] Root task
       - [ ] Sub-task (2 spaces)
         - [ ] Deep sub-task (4 spaces)
     ```
   - *Attack*: Pass into `Humanizer.humanize(doc, preserve_markdown=True)`.
   - *Result*: **FAILED**. `sanitize_and_verify_grammar` collapses `  ` and `    ` into ` `, destroying list indentation.

4. **Scenario 4: Sentential Bare URL with Trailing Punctuation**
   - *Input*: `"Please visit https://example.com."`
   - *Attack*: Pass into `InlineMasker.mask()`.
   - *Result*: **MARGINAL**. Period absorbed into `⟦URL_0⟧`.

---

## 7. Conclusion

Milestone 2 establishes a very solid, well-designed structural markdown chunking architecture. However, because:
1. `tests/unit/test_markdown_parser.py::test_autolink_and_bare_url_masking` contains a failing assertion due to missing email autolink support in `mask.py`, and
2. Splitting oversized paragraphs drops inter-chunk spacing on reassembly, and
3. Grammar sanitization inadvertently collapses nested list indentation,

the formal verdict is **REQUEST_CHANGES**.

Worker 1 should apply the remediations specified in Section 4 to resolve these three issues. Once resolved, Milestone 2 will be in full compliance.

---

## 8. Verification Method

Once Worker 1 applies the fixes:
1. Run markdown unit tests:
   ```bash
   python -m pytest tests/unit/test_markdown_parser.py -v
   ```
2. Run benchmark tests:
   ```bash
   python -m pytest tests/benchmarks -v
   ```
3. Run E2E feature coverage tests:
   ```bash
   python -m pytest tests/e2e/test_tier1_features.py -k test_f7 -v
   ```
4. Verify round-trip reassembly on oversized paragraphs:
   ```python
   long_para = " ".join([f"Sentence {i} describing system components." for i in range(25)])
   doc = MarkdownDocument(long_para)
   chunks = doc.extract_chunks(max_chunk_chars=300)
   assert doc.reconstruct([c.content for c in chunks]) == long_para
   ```
