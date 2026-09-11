# Handoff Report — Milestone 2 Adversarial Challenge: Markdown & Structural Chunking

**Verdict**: **REJECT**

---

## 1. Observation

### Obs 1: Missing Sentence-Separator Whitespace in Oversized Paragraph Reconstruction
- **File**: `src/humanizer/parser/markdown.py`, lines 558-598 (`MarkdownDocument.extract_chunks`) and lines 635-644 (`MarkdownDocument.reconstruct`).
- **Verbatim Code**:
  ```python
  # Line 569-580
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
  ```
  ```python
  # Lines 635-644
  if len(humanized_chunks) == len(self.chunks):
      out_pieces: list[str] = []
      for chunk, h_text in zip(self.chunks, humanized_chunks):
          if not chunk.is_humanizable:
              out_pieces.append(chunk.raw_text)
          else:
              out_pieces.append(h_text)
      return "".join(out_pieces)
  ```
- **Observed Behavior**:
  `sub_content` for non-terminal sub-chunks terminates immediately after the final sentence's period (e.g. `"...runtime."`). No trailing space or newline delimiter is attached.
  When `reconstruct()` executes `"".join(out_pieces)`, chunk `k` ending in `"...runtime."` and chunk `k+1` beginning with `"Sentence number 05..."` are concatenated directly with no space, yielding `"...runtime.Sentence number 05..."`.
  In `tests/unit/test_markdown_stress.py::TestMarkdownStressHarness::test_oversized_paragraph_reconstruction_no_lost_spaces`, the space between sentence boundaries across chunks is lost, corrupting the document text.

### Obs 2: Destruction of Nested List Indentation under Humanization
- **File**: `src/humanizer/engine/guardrails.py`, lines 330-335 (`sanitize_and_verify_grammar`), and `src/humanizer/client.py`, lines 343-351 (`Humanizer.humanize`).
- **Verbatim Code**:
  ```python
  # src/humanizer/engine/guardrails.py, lines 330-335
  # 3. Collapse double and multiple horizontal spaces: 'word  word' -> 'word word'
  double_spaces = re.compile(r"[ \t]{2,}")
  if double_spaces.search(repaired):
      issues.append("Extraneous consecutive whitespace detected.")
      repaired = double_spaces.sub(" ", repaired)
  ```
- **Observed Behavior**:
  `MarkdownDocument.extract_chunks` groups contiguous list items into a single humanizable `DocumentChunk`.
  During `client.humanize(..., preserve_markdown=True)`, humanizable chunks are routed through `sanitize_and_verify_grammar(clean_text)`.
  The regex `[ \t]{2,}` replaces any sequence of 2 or more horizontal spaces with a single space `" "`, including leading line indentation.
  Consequently:
  `"  - Level 2 item A"` (2 spaces) becomes `" - Level 2 item A"` (1 space).
  `"    - Level 3 item A1"` (4 spaces) becomes `" - Level 3 item A1"` (1 space).
  Furthermore, `MarkdownDocument.reconstruct` directly concatenates chunk strings and never invokes `ListItemBlock.render(humanized_content)` (which was written to preserve `self.indent` at line 203 of `markdown.py`), rendering the block's indentation logic dead code.
  In `tests/unit/test_markdown_stress.py::TestMarkdownStressHarness::test_deeply_nested_lists_client_humanize_indentation_preservation`, all nested lists lose indentation hierarchy.

### Obs 3: False Positive Math Classification on Currency Expressions
- **File**: `src/humanizer/parser/mask.py`, line 33 (`InlineMasker.INLINE_MATH_REGEX`).
- **Verbatim Code**:
  ```python
  # Line 33
  INLINE_MATH_REGEX = re.compile(r"(?<!\$)\$([^$\n]+?)\$(?!\$)")
  ```
- **Observed Behavior**:
  Given prose such as `"The budget mode costs $50 in API credits and saves $10 per batch."`, the regex matches the substring between the two currency signs:
  `$50 in API credits and saves $`.
  This is masked as `⟦MATH_0⟧`.
  Any normal English prose between two dollar amounts is shielded from humanization. Moreover, if banned AI buzzwords (e.g. `"delve"`, `"tapestry"`, `"moreover"`) appear between dollar signs, they are masked as math tokens and bypass the 0-tolerance buzzword audit.

### Obs 4: Multi-Page Documents, Fenced Code, and Table Invariance (Verified Strengths)
- **Files**: `src/humanizer/parser/markdown.py`, `src/humanizer/parser/mask.py`.
- **Observed Behavior**:
  - Documents >50,000 characters with 25+ sections parse in linear O(N) time and memory.
  - Fenced code blocks (```` and ~~~) and GFM tables (`| ... |`) with alignment markers (`:---:`) and embedded backtick pipes are correctly isolated into immutable chunks (`is_humanizable=False`).
  - `MarkdownDocument.reconstruct` restores code blocks and tables 100% byte-for-byte identical to source text.
  - Headers (# through ######) successfully trigger section boundary flushes.

---

## 2. Logic Chain

1. **Requirement R3 & Project Specification**:
   `ORIGINAL_REQUEST.md § R3` and `PROJECT.md § M2` require:
   - "Automatically partition long texts (articles, multi-page papers) along semantic paragraph boundaries while preserving markdown structure (headers, lists, tables) and leaving code blocks completely untouched."
   - "Verify that chunks split cleanly along paragraph boundaries without bisecting code blocks or tables, and reconstruct without losing content or adding spurious whitespace."
2. **Reconstruction Failure (Obs 1)**:
   When an article contains oversized paragraphs (>1500 chars), `extract_chunks` splits along sentence boundaries. Because sub-chunks do not retain trailing whitespace and `reconstruct()` uses an empty delimiter `"".join()`, sentence boundaries across chunks lose their spaces (e.g. `"concept.Sentence"`). This constitutes loss of content / formatting corruption.
3. **Hierarchy Destruction (Obs 2)**:
   Markdown nested lists convey hierarchical relationships through indentation (2 or 4 spaces). When `sanitize_and_verify_grammar` blindly collapses `[ \t]{2,}` without checking whether spaces are leading line indentation, it flattens all nested list items into top-level items with a single space (`" - "`). Because `reconstruct()` does not use `ListItemBlock.render()`, this data loss is permanent.
4. **Vocabulary Audit Bypass (Obs 3)**:
   Greedy inline math matching across arbitrary currency dollar signs masks standard prose as `⟦MATH_0⟧`, creating an evasion vector where AI clichés within currency contexts bypass the required vocabulary audit.

---

## 3. Caveats

- Unmodified documents with paragraphs strictly under `max_chunk_chars` (1500 chars) that do not use nested lists or currency symbols reconstruct losslessly.
- Fenced code blocks and GFM markdown tables are robust and completely protected.
- The issues identified are focused specifically on chunk boundary reconstruction, indentation preservation under guardrails, and inline math regex specificity.

---

## 4. Conclusion

**VERDICT: REJECT**

Milestone 2 cannot be approved in its current state due to two critical defects (whitespace loss on oversized paragraph splits and nested list indentation flattening) and one medium defect (currency misclassification in inline math masking).

### Required Mitigations for Milestone 2 Worker:
1. **Fix Sentence Boundary Whitespace**:
   In `src/humanizer/parser/markdown.py` (lines 569-588), append a trailing space `" "` (or appropriate intra-paragraph separator) to non-terminal sentence sub-chunks, or record an `is_subchunk` continuation flag so that `reconstruct()` preserves spaces between sentences.
2. **Fix Nested List Indentation**:
   In `src/humanizer/engine/guardrails.py` (line 331), update `double_spaces` to preserve leading indentation at the beginning of lines (e.g., using `(?<!^)(?<!\n)[ \t]{2,}` or excluding markdown bullet indentation lines from multi-space collapsing). Ensure `ListItemBlock.indent` is honored.
3. **Fix Math vs Currency Regex**:
   In `src/humanizer/parser/mask.py` (line 33), adjust `INLINE_MATH_REGEX` to follow CommonMark/LaTeX math conventions (e.g., `(?<!\$)\$(?!\s)([^$\n]+?)(?<!\s)\$(?!\$)`, requiring non-whitespace after the opening `$` and before the closing `$`, and not matching currency patterns like `\$\d+`).

---

## 5. Verification Method

1. Inspect the stress test harness:
   `tests/unit/test_markdown_stress.py`
2. Run pytest on the stress suite once terminal permissions allow:
   `pytest tests/unit/test_markdown_stress.py -v`
   - `test_oversized_paragraph_reconstruction_no_lost_spaces` reproduces the missing space bug.
   - `test_deeply_nested_lists_client_humanize_indentation_preservation` reproduces the nested list flattening bug.
   - `test_currency_symbol_misclassification_as_math` reproduces the currency mask bug.
3. Invalidation condition:
   If all three tests in `tests/unit/test_markdown_stress.py` pass cleanly alongside `tests/unit/test_markdown_parser.py` and `tests/unit/test_adversarial_m2.py`, the rejection is invalidated and M2 may be confirmed.
