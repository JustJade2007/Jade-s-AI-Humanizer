## 2026-09-10T09:28:35Z
You are a Worker (`teamwork_preview_worker`) implementing Milestone 1 Iteration 2 (Core Engine & Guardrails Remediation) for Jade's AI Humanizer.
Your working directory is:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m1_2

MANDATORY FIRST STEP: Read the authoritative requirements in:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\ORIGINAL_REQUEST.md

Also read:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\PROJECT.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_m1_it2_1\remediation_client.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_m1_it2_2\remediation_guardrails.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_m1_it2_3\remediation_grammar_generator.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission:
Apply the exact remediations designed by the 3 Explorers:
1. In `src/humanizer/client.py`:
   - Assign public attributes: `self.model`, `self.fallback_model`, `self.api_key`, `self.mock_mode`.
   - In `_post_process`, ensure `_restore_code_blocks` is invoked as the absolute last step after buzzwords replacement and grammar sanitization.
   - In `humanize_stream`, integrate `StreamChunkAccumulator` (buffered streaming) to prevent placeholder fragmentation (e.g. `⟦CODE_` + `FENCE_0⟧`) and buzzwords split across chunk boundaries.
2. In `src/humanizer/engine/guardrails.py`:
   - Upgrade word boundary matching to lookarounds `(?<![a-zA-Z0-9])` and `(?![a-zA-Z0-9])` so italicized buzzwords (`_delve_`, `*tapestry*`) and hyphenated terms (`multi-faceted`) are properly captured and replaced while preserving formatting.
   - Add missing terms: `nuanced` -> `subtle`, `symphonies of` -> `harmonies of`, standalone `serves as a reminder` -> `reminds us`.
   - Disaggregate subject-verb agreement rules for `showcases` (singular) vs `showcase` (plural/base), and `underscores` vs `underscore`.
   - Hardened `sanitize_and_verify_grammar`: whitelist valid doubled words (`had had`, `that that`, `Bora Bora`), whitelist abbreviations (`e.g.`, `i.e.`), normalize double spaces (`"  "` -> `" "`), and repair unmatched/dangling double quotation marks.
   - Fix assertion typo in `tests/unit/test_adversarial_guardrails.py:173` if needed (e.g. "e.g. pencils" should remain lowercase).
3. In `src/humanizer/engine/generator.py`:
   - Add streaming fallback logic to `self.fallback_model` in `generate_stream_sync` and `generate_stream_async` upon primary model failure before yielding.
4. Run comprehensive test verification:
   - Run `python -m pytest tests/unit tests/benchmarks -v` via terminal and ensure all tests pass (including `test_adversarial_engine.py` and `test_adversarial_guardrails.py`).
5. Write your handoff report to:
`c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m1_2\handoff.md`
When done, send a message to orchestrator with your findings.
