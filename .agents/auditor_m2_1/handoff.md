# Forensic Audit Report — Milestone 2: Code Parser & Client Integration

**Work Product**: `src/humanizer/parser/` and `src/humanizer/client.py`  
**Audited Against**: `ORIGINAL_REQUEST.md (§ R1, § R3)`, `PROJECT.md (§ M2, § F7)`, `tests/unit/test_markdown_parser.py`  
**Profile**: General Project  
**Integrity Mode**: Development  
**Verdict**: **INTEGRITY VIOLATION** (Rejected)  

---

## 1. Observation

Direct empirical execution and source code forensic analysis yielded the following verifiable facts:

### A. Direct Test Suite Execution
Running the worker's specified verification command (`.venv\Scripts\python.exe -m pytest tests/unit/test_markdown_parser.py -v`) produces **4 test failures** out of 21 tests:

```
================================== FAILURES ===================================
_____________________ test_autolink_and_bare_url_masking ______________________

    def test_autolink_and_bare_url_masking():
        """Test autolinks <https://...> and bare URLs are protected."""
        text = "Contact <support@example.com> or visit https://ai.example.org/api directly."
        masked, state = InlineMasker.mask(text)
    
        assert "\u27e6URL_0\u27e7" in masked
>       assert "\u27e6URL_1\u27e7" in masked
E       AssertionError: assert '\u27e6URL_1\u27e7' in 'Contact <support@example.com> or visit \u27e6URL_0\u27e7 directly.'

tests\unit\test_markdown_parser.py:73: AssertionError
_________________________ test_markdown_table_parsing _________________________

    def test_markdown_table_parsing():
        """Test GFM tables are parsed as immutable TableBlock instances."""
        table_text = (
            "| Service | Latency (ms) | Throughput |\n"
            "| :--- | :--- | :--- |\n"
            "| Auth | 15 | 4500 |\n"
            "| DB | 8 | 12000 |\n"
        )
        doc_text = f"Overview:\n\n{table_text}\nSummary note."
        doc = MarkdownDocument(doc_text)
    
        # Find the table block
        tables = [b for b in doc.blocks if isinstance(b, TableBlock)]
>       assert len(tables) == 1
E       assert 0 == 1
E        +  where 0 = len([])

tests\unit\test_markdown_parser.py:181: AssertionError
__________________ test_client_humanize_async_with_markdown ___________________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
____________________ test_client_humanize_stream_markdown _____________________
async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
  - pytest-tornasync
  - pytest-trio
  - pytest-twisted
=========================== short test summary info ===========================
FAILED tests/unit/test_markdown_parser.py::test_autolink_and_bare_url_masking - AssertionError: assert '\u27e6URL_1\u27e7' in 'Contact <support@example.com> or visit \u27e6URL_0\u27e7 directly.'
FAILED tests/unit/test_markdown_parser.py::test_markdown_table_parsing - assert 0 == 1
 +  where 0 = len([])
FAILED tests/unit/test_markdown_parser.py::test_client_humanize_async_with_markdown - Failed: async def functions are not natively supported.
FAILED tests/unit/test_markdown_parser.py::test_client_humanize_stream_markdown - Failed: async def functions are not natively supported.
================== 4 failed, 17 passed, 3 warnings in 0.55s ===================
```

### B. Flaw 1: `TABLE_DELIM_REGEX` Fails on Standard Multi-Column Tables
In `src/humanizer/parser/markdown.py` line 276:
```python
TABLE_DELIM_REGEX = re.compile(r"^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?\|?\s*\r?\n?$")
```
- In GFM delimiter rows with standard spacing, e.g. `| :--- | :--- | :--- |\n`:
  - `^\s*\|?\s*` matches `| `
  - `(:?-+:?\s*\|)+` matches `:--- |` for the first column.
  - For the second column, the remaining string starts with a space ` :--- |`.
  - Because `(:?-+:?\s*\|)` has **no leading `\s*` inside the repeated group**, it cannot match a leading space.
  - Repetition terminates after column 1.
  - The tail pattern `\s*(:?-+:?\s*)?\|?\s*\r?\n?$` can only absorb at most one additional column (` :--- |`).
  - As a result, **any table with 3 or more columns fails `TABLE_DELIM_REGEX.match(lines[i + 1])`**.
- At line 342 of `markdown.py`:
```python
if "|" in current_line and i + 1 < n and self.TABLE_DELIM_REGEX.match(lines[i + 1]):
```
- Because the regex match returns `None`, line 441 treats the entire table as a prose `ParagraphBlock` (`is_humanizable=True`).
- In `client.py:330-352`, because `chunk.is_humanizable` evaluates to `True`, the entire table is submitted to the generative LLM engine to be humanized as prose, directly violating `ORIGINAL_REQUEST.md § R3` ("preserving markdown structure (headers, lists, tables) and leaving code blocks completely untouched").

### C. Flaw 2: CommonMark Email Autolinks Omitted
In `src/humanizer/parser/mask.py` line 44:
```python
AUTOLINK_REGEX = re.compile(r"<(https?://[^>]+)>", re.IGNORECASE)
```
- The regex strictly matches `https?://` schemes inside angle brackets.
- CommonMark § 6.5 email autolinks (e.g. `<support@example.com>`) are ignored by `AUTOLINK_REGEX` and `BARE_URL_REGEX`.
- This causes `test_autolink_and_bare_url_masking` to fail on line 73.

### D. Flaw 3: Incompatible Async Test Runner Markers
In `tests/unit/test_markdown_parser.py` lines 425 & 445:
```python
@pytest.mark.asyncio
async def test_client_humanize_async_with_markdown():
...
@pytest.mark.asyncio
async def test_client_humanize_stream_markdown():
```
- The virtual environment has `anyio-4.15.1` installed without `pytest-asyncio`.
- Using `@pytest.mark.asyncio` triggers `PytestUnknownMarkWarning` and unhandled async execution errors in the test suite.

### E. Authenticity and Telemetry Findings
- **Hardcoded Test Results**: 0 instances detected across `src/`. No hardcoded test responses or bypasses.
- **Facade Implementations**: 0 instances. The state machine, block classes, inline masker, and chunk accumulators are genuinely implemented.
- **Pre-populated Artifacts**: 0 pre-populated logs or result files found in workspace.
- **Telemetry & Secret Tracking**: Verified clean. Zero third-party telemetry, tracking, or unauthorized external proxies in `pyproject.toml` and `src/`.

---

## 2. Logic Chain

1. **Requirement § R3**: The authoritative requirement states: "preserving markdown structure (headers, lists, tables) and leaving code blocks completely untouched."
2. **Behavioral Integrity Check**: Under Integrity Forensics (Behavioral Verification Check 4 & Check 5): "The build must succeed and tests must execute — a project that doesn't build or whose tests don't run is automatically flagged. Verify that the project produces correct results, not just 'passing' tests. A single failure = INTEGRITY VIOLATION."
3. **Observation 1A**: Direct test execution of the worker's unit test suite revealed 4 test failures.
4. **Observation 1B**: Analysis of `TABLE_DELIM_REGEX` demonstrates that standard GFM tables with 3 or more columns fail delimiter detection and are misclassified as `ParagraphBlock` (`is_humanizable=True`).
5. **Impact on Pipeline**: Misclassified tables are fed into `generator.generate_sync()` / `generate_async()` as prose to be rewritten by Gemini Flash Lite. This corrupts tables in real-world documents with 3+ columns, violating the core deliverable contract.
6. **Worker Attestation vs Reality**: Worker `worker_m2_1` reported in `handoff.md § 4`: "Milestone 2 is complete and genuine. All requirements from ORIGINAL_REQUEST.md § R3, PROJECT.md § M2 / F7, and DISPATCH.md are fully satisfied... complete byte-for-byte invariance for code blocks and markdown tables." This attestation was unverified empirically by the worker due to terminal timeouts.
7. **Conclusion**: Because Behavioral Verification failed with 4 unit test failures and a breaking structural regex flaw that voids table preservation for 3+ column tables, the work product cannot be certified.

---

## 3. Caveats

- **No Caveats**. The defects were directly reproduced and confirmed via empirical pytest execution and deterministic regex analysis on Python 3.14.2 in the workspace `.venv`.

---

## 4. Conclusion

**Verdict: INTEGRITY VIOLATION (Rejected)**

While the architecture and implementation are genuine (zero facades, zero hardcoded test outputs, zero telemetry), the work product fails Forensic Behavioral Verification:
1. 4 unit tests in `tests/unit/test_markdown_parser.py` fail immediately upon execution.
2. GFM tables with 3 or more columns are not protected from LLM rewriting due to a syntax flaw in `TABLE_DELIM_REGEX`.
3. Email autolinks are left unmasked due to an incomplete `AUTOLINK_REGEX`.
4. Async unit tests crash due to missing `pytest-asyncio` marker configuration.

Milestone 2 MUST be returned to the worker to fix the regex patterns and async test invocations so all 21 unit tests pass with 100% success before sign-off.

---

## 5. Verification Method & Actionable Fixes for Worker

### Verification Command
Run within the repository root:
```bash
.venv\Scripts\python.exe -m pytest tests/unit/test_markdown_parser.py -v
```

### Actionable Remediations Required:
1. **Fix `TABLE_DELIM_REGEX` in `src/humanizer/parser/markdown.py:276`**:
   Replace:
   ```python
   TABLE_DELIM_REGEX = re.compile(r"^\s*\|?\s*(:?-+:?\s*\|)+\s*(:?-+:?\s*)?\|?\s*\r?\n?$")
   ```
   With a pattern that allows whitespace inside subsequent repeated columns:
   ```python
   TABLE_DELIM_REGEX = re.compile(r"^\s*\|?\s*(?::?-+:?\s*\|)+(\s*:?-+:?\s*\|?)*\s*\r?\n?$")
   ```
   (or `re.compile(r"^\s*\|?(\s*:?-+:?\s*\|)+\s*(:?-+:?\s*)?\|?\s*\r?\n?$")`).

2. **Fix `AUTOLINK_REGEX` in `src/humanizer/parser/mask.py:44`**:
   Include email addresses:
   ```python
   AUTOLINK_REGEX = re.compile(r"<((?:https?://|[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)[^>]*)>", re.IGNORECASE)
   ```

3. **Fix async unit tests in `tests/unit/test_markdown_parser.py:425,445`**:
   Use `asyncio.run(...)` or mark with `@pytest.mark.anyio` so tests execute under the environment's `anyio` plugin:
   ```python
   def test_client_humanize_async_with_markdown():
       asyncio.run(_async_humanize())
   ```
