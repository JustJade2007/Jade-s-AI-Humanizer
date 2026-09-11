# Handoff Report — Milestone 2 Adversarial Challenge

**Verdict**: **REJECT**

---

## 1. Observation

### Observation 1.1: Indented 4-Space Code Blocks Classified as Humanizable Paragraphs
In `src/humanizer/parser/markdown.py`, lines 298-466 define `_parse_blocks(self, text: str)`:
```python
# 1. Fenced Code Block Detection
fence_match = self.OPEN_FENCE_REGEX.match(current_line)
...
# 9. Paragraph Block (Consolidates contiguous regular prose lines)
para_lines = [current_line]
j = i + 1
while j < n:
    next_line = lines[j]
    if (
        self.OPEN_FENCE_REGEX.match(next_line)
        or ("|" in next_line and j + 1 < n and self.TABLE_DELIM_REGEX.match(lines[j + 1]))
        or self.BLANK_LINE_REGEX.match(next_line)
        or self.SEPARATOR_REGEX.match(next_line)
        or self.ATX_HEADER_REGEX.match(next_line)
        or self.LIST_ITEM_UNORDERED_REGEX.match(next_line)
        or self.LIST_ITEM_ORDERED_REGEX.match(next_line)
        or self.QUOTE_REGEX.match(next_line)
    ):
        break
    para_lines.append(next_line)
    j += 1

raw_para = "".join(para_lines)
content = raw_para.rstrip("\r\n")
suffix = raw_para[len(content):]
blocks.append(ParagraphBlock(raw_text=raw_para, content=content, suffix=suffix))
```
- No parser exists for indented code blocks (4 spaces or 1 tab, per CommonMark §4.4 and GFM §4.4).
- When a 4-space indented code block (e.g. `    def compute():\n        return 42\n`) is passed to `MarkdownDocument`, it is classified as `ParagraphBlock` with `is_humanizable = True`.
- In `src/humanizer/client.py` lines 335-350, humanizable chunks are passed to `self.generator.generate_sync()`, `replace_banned_buzzwords()`, and `sanitize_and_verify_grammar()`.
- Empirical consequence: 4-space indented code blocks are modified, buzzwords in code comments are replaced, and code syntax is damaged by the grammar sanitizer. They are NOT 100% byte-for-byte preserved.

### Observation 1.2: Oversized Paragraph Sentence Splitting Drops Separator Whitespace
In `src/humanizer/parser/markdown.py` lines 561-597:
```python
if block.block_type == BlockType.PARAGRAPH and block_len > max_chunk_chars:
    _flush_acc()
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
```
- `SENTENCE_SPLIT_LOOKBEHIND = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")` splits sentences and consumes the separating whitespace.
- For all intermediate sub-chunks (before the final sub-chunk), `sub_content = " ".join(sub_acc)` is appended with NO trailing whitespace or newline.
- In `reconstruct()` lines 642-643: `out_pieces.append(h_text)` followed by `"".join(out_pieces)`.
- When sub-chunk 0 ends with `"sentence one."` and sub-chunk 1 starts with `"Sentence two."`, `"".join()` concatenates them into `"sentence one.Sentence two."` without any space between the sentences.

### Observation 1.3: Unclosed Code Fence Truncates Last Line in `block.code`
In `src/humanizer/parser/markdown.py` lines 318-328:
```python
j = i + 1
while j < n:
    if close_regex.match(lines[j]):
        j += 1
        break
    j += 1

raw_code = "".join(lines[i:j])
body_lines = lines[i + 1 : j - 1] if j - 1 > i else []
code_body = "".join(body_lines)
```
- When an unclosed fence reaches EOF (`j == n`), `lines[j-1]` is the final line of code, not a closing fence delimiter.
- Slicing `lines[i + 1 : j - 1]` drops `lines[j - 1]`, leaving `block.code` missing its last line. (Note: `block.raw_text` includes all lines, so document reconstruction retains the raw text, but internal code inspection via `block.code` suffers data loss).

### Observation 1.4: `preserve_markdown=False` Misses Tilde Fences (`~~~`)
In `src/humanizer/client.py` lines 218-228:
```python
def _protect_code_blocks(self, text: str) -> tuple[str, list[str]]:
    """Safeguard fenced code blocks from modification."""
    fences: list[str] = []

    def _repl(m: re.Match[str]) -> str:
        fences.append(m.group(0))
        return f"⟦CODE_FENCE_{len(fences)-1}⟧"

    protected = re.sub(r"```[\s\S]*?```", _repl, text)
    return protected, fences
```
- Regex `r"```[\s\S]*?```"` only protects triple-backtick fences; `~~~` tilde fences are ignored in `_protect_code_blocks`, `DeepParaphraser.apply_burstiness_variation` (`src/humanizer/engine/deep.py` line 86), and `_strip_markdown_and_code` (`src/humanizer/engine/readability.py` line 58).

### Observation 1.5: Tables Inside Blockquotes Are Not Recognized as `TableBlock`
In `src/humanizer/parser/markdown.py` line 342:
`if "|" in current_line and i + 1 < n and self.TABLE_DELIM_REGEX.match(lines[i + 1]):`
- Where `TABLE_DELIM_REGEX = re.compile(r"^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?\|?\s*\r?\n?$")`.
- When a table is quoted (e.g. `> | Header | Header |\n> | --- | --- |`), the leading `> ` causes `TABLE_DELIM_REGEX` to fail.
- Quoted table rows are parsed as individual `QuoteBlock` instances (`is_humanizable = True`) and passed to the LLM for prose rewriting.

### Observation 1.6: Fenced Code Blocks and GFM Tables (Standalone) Are 100% Invariant
- Fenced code blocks (```` ``` ```` and `~~~`) with language specifiers are identified and emitted as `CodeBlock` (`is_humanizable = False`).
- Banned AI buzzwords in code comments and string literals within fenced code blocks remain 100% unmodified.
- Standalone GFM tables with header rows, alignment delimiters (`:---:`, `:---`, `---:`), and embedded pipes in code spans (`| `a | b` |`) or escaped pipes (`\|`) are identified and emitted as `TableBlock` (`is_humanizable = False`).
- In `reconstruct()`, `chunk.raw_text` is used for all non-humanizable chunks, achieving 100% byte-for-byte fidelity for these elements.

---

## 2. Logic Chain

1. **Premise 1 (Prompt Contract & R3)**: The mission explicitly states:
   - "Test fenced code blocks with language specifiers, unclosed code fences, tilde fences (`~~~`), indented 4-space blocks, and code blocks containing buzzwords in comments or string literals."
   - "Empirically verify that every single code block and table is 100% byte-for-byte identical after humanization."
2. **Premise 2 (Obs 1.1)**: `src/humanizer/parser/markdown.py` lacks support for indented 4-space code blocks. Any text indented by 4 spaces is treated as `ParagraphBlock` with `is_humanizable = True`.
3. **Premise 3 (Obs 1.1)**: During humanization, humanizable chunks are processed by `self.generator`, `replace_banned_buzzwords()`, and `sanitize_and_verify_grammar()`. Consequently, indented code blocks are mutated and corrupted. This directly violates the 100% byte-for-byte invariant for code blocks.
4. **Premise 4 (Obs 1.2)**: For documents containing paragraphs exceeding `max_chunk_chars` (1500 chars), splitting by sentence lookbehind consumes the inter-sentence whitespace without restoring it between adjacent sub-chunks. Document reconstruction results in sentences running together without spaces (`"word.Next"`).
5. **Premise 5 (Obs 1.3, 1.4, 1.5)**: Unclosed code fences lose the final line of `block.code`, tilde fences are vulnerable when `preserve_markdown=False`, and tables in blockquotes are treated as prose.
6. **Conclusion**: Milestone 2 cannot be confirmed while indented 4-space code blocks and oversized paragraph sentence boundaries are corrupted.

---

## 3. Caveats

- For standard standalone fenced code blocks (both ``` and ~~~) and standalone GFM tables (with alignment and embedded pipes), byte-for-byte preservation in `preserve_markdown=True` mode is verified and robust.
- The missing indented code block parser is an omission in `_parse_blocks`; resolving it requires recognizing lines preceded by 4 spaces or 1 tab following an empty line or block start as `CodeBlock(is_humanizable=False)`.
- Live Gemini API calls were not executed as part of this challenge due to offline test isolation requirements; verification used the deterministic offline generator and rigorous code-path tracing.

---

## 4. Conclusion

**Verdict: REJECT**

Milestone 2 fails the acceptance criteria on:
1. **Indented 4-space code block preservation**: Indented code blocks are parsed as prose paragraphs and subjected to LLM humanization, buzzword synonym substitution, and grammar modification.
2. **Oversized paragraph reconstruction**: Paragraphs exceeding 1500 characters lose inter-sentence whitespace at sub-chunk boundaries during reconstruction.

### Required Actions for Worker to Pass:
1. **Implement Indented Code Block Detection in `_parse_blocks()`**:
   - Detect sequences of lines indented by 4 spaces (`^[ ]{4,}`) or 1 tab following a blank line or document start.
   - Emit them as `CodeBlock(raw_text=raw_indented, is_humanizable=False)`.
2. **Fix Sentence-Chunk Boundary Whitespace in `extract_chunks()`**:
   - When splitting an oversized paragraph into sub-chunks, ensure intermediate sub-chunks retain trailing whitespace (e.g. `" "`) or that `reconstruct()` joins paragraph sub-chunks of the same block with `" "`.
3. **Fix `code_body` in Unclosed Fences**:
   - In `_parse_blocks()` for code fences, if `close_regex.match(lines[j])` is False upon reaching EOF, set `body_lines = lines[i + 1 : j]` instead of `lines[i + 1 : j - 1]`.
4. **Update `_protect_code_blocks` and Paraphraser for Tilde Fences**:
   - In `client.py` and `deep.py`, support `~~~[\s\S]*?~~~` alongside ```` ```[\s\S]*?``` ````.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Indented 4-Space Code Block Corruption**:
   Inspect `src/humanizer/parser/markdown.py` lines 298-466. Note the complete absence of `^[ ]{4,}` handling before `ParagraphBlock`.
   Run with:
   ```python
   from humanizer import Humanizer
   h = Humanizer(mock_mode=True)
   md = "Prose\n\n    def test():\n        # delve into tapestry\n        return 1\n\nEnd"
   res = h.humanize(md, preserve_markdown=True)
   assert "    def test():" in res.text  # Observe failure or altered buzzwords
   ```

2. **Verify Paragraph Sentence Whitespace Drop**:
   Create a paragraph with 40 sentences totaling >1500 chars. Run through `MarkdownDocument(text).extract_chunks()` and `reconstruct()`. Note that sentences spanning chunk boundaries are joined as `sentence1.sentence2` without an intervening space.

3. **Verify Standalone Fenced Code and Table Invariance**:
   Run `tests/unit/test_adversarial_m2.py` via standard library `unittest` (`python -m unittest tests/unit/test_adversarial_m2.py`).
