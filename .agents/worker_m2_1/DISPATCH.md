## 2026-09-10T09:43:32Z
You are a Worker (`teamwork_preview_worker`) implementing Milestone 2 (Structural & Markdown Document Chunking) for Jade's AI Humanizer.
Your working directory is:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m2_1

MANDATORY FIRST STEP: Read the authoritative requirements in:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\ORIGINAL_REQUEST.md

Also read:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\PROJECT.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_3\survey_architecture_packaging.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\src\humanizer\client.py

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission:
1. Implement `src/humanizer/parser/mask.py`:
   - Inline code masking (`⟦INLINE_CODE_X⟧`) and link masking (`⟦URL_X⟧`) so inline backtick code and markdown URLs are protected from LLM alteration.
2. Implement `src/humanizer/parser/markdown.py`:
   - Two-tier block parser separating immutable blocks (`CodeBlock`, `TableBlock`, `BlankLineBlock`, `SeparatorBlock`) from humanizable blocks (`HeaderBlock`, `ListItemBlock`, `ParagraphBlock`, `QuoteBlock`).
   - Semantic paragraph chunking: partition long documents (multi-page articles) along semantic paragraph boundaries without ever bisecting code blocks or tables.
   - Document reconstructor: reassemble humanized chunks back into the complete markdown document with headers, lists, tables preserved, and code blocks 100% byte-for-byte identical to the original source.
3. Integrate with `src/humanizer/client.py`:
   - In `humanize`, `humanize_async`, and `humanize_stream`, when `preserve_markdown=True`, utilize the parser to humanize prose while keeping markdown structure intact.
4. Unit Tests:
   - Create `tests/unit/test_markdown_parser.py` thoroughly exercising code block invariance, table preservation, header/list preservation, inline code masking, and long document chunking.
   - Run tests via terminal: `python -m pytest tests/unit/test_markdown_parser.py tests/unit tests/benchmarks -v` and verify all tests pass.
   - Also test E2E F7 tests: `python -m pytest tests/e2e/test_tier1_features.py -k test_f7 -v`.
5. Write your handoff report to:
`c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m2_1\handoff.md`
When done, send a message to orchestrator with your findings.
