## 2026-09-10T08:58:05Z

You are a Worker (`teamwork_preview_worker`) implementing Milestone 1 (Core Engine & Guardrails) for Jade's AI Humanizer.
Your working directory is:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m1_1

MANDATORY FIRST STEP: Read the authoritative requirements in:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\ORIGINAL_REQUEST.md

Also read:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\PROJECT.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_1\survey_environment.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_2\survey_engine.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_3\survey_architecture_packaging.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Mission:
1. Environment & Dependencies:
   - Ensure the project virtual environment / Python environment has required packages installed (`google-genai`, `pydantic`, `fastapi`, `uvicorn`, `pytest`, `httpx`). Install them if missing.
   - Create `pyproject.toml` with project metadata, dependencies, and package definitions for `src/humanizer`.
2. Implement Milestone 1 modules in `src/humanizer/`:
   - `src/humanizer/__init__.py`: Export `Humanizer`, `HumanizeResult`.
   - `src/humanizer/models.py`: Pydantic models / dataclasses (`HumanizeResult`, `TonePreset`, `ReadingLevelPreset`, etc.).
   - `src/humanizer/engine/prompt.py`: Token-minimized system instructions (<100 prompt tokens overhead per request in `budget` mode) and style presets (`neutral`, `casual`, `academic`, `professional`, reading levels).
   - `src/humanizer/engine/readability.py`: Pure-Python Flesch-Kincaid & Flesch Reading Ease calculations.
   - `src/humanizer/engine/guardrails.py`: 0-tolerance banned AI buzzwords audit (delve, tapestry, in summary, moreover, testament, etc.) with automated replacement heuristics; automated grammar/syntax verification.
   - `src/humanizer/engine/deep.py`: Multi-layered paraphrasing engine (burstiness variation, perplexity shifting).
   - `src/humanizer/engine/generator.py`: Gemini client wrapper using official `google-genai` SDK (`gemini-2.5-flash-lite`, fallback `gemini-2.0-flash-lite`), sync and async generation, streaming generator, with offline mock engine & token simulator when no API key is set or `mock_mode=True`.
   - `src/humanizer/client.py`: Core `Humanizer` class with sync (`humanize`), async (`humanize_async`), and streaming (`humanize_stream`) methods conforming to `PROJECT.md § Interface Contracts`.
3. Unit Tests & Benchmarks:
   - Create `tests/unit/test_engine.py` and `tests/unit/test_guardrails.py` verifying all M1 functionality.
   - Create `tests/benchmarks/test_token_overhead.py` strictly verifying that `budget` mode operates under <100 prompt tokens overhead per request.
   - Create `tests/benchmarks/test_vocabulary_audit.py` verifying 0 banned AI buzzwords in output.
4. Verify: Run `pytest tests/unit tests/benchmarks` and verify all tests pass with exit code 0.

Exclusive File Ownership:
You own:
- `pyproject.toml`
- `src/humanizer/__init__.py`, `src/humanizer/client.py`, `src/humanizer/models.py`, `src/humanizer/engine/`
- `tests/unit/test_engine.py`, `tests/unit/test_guardrails.py`, `tests/benchmarks/`

Record your progress in your `progress.md` and write your complete handoff report to `c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\worker_m1_1\handoff.md`.
When done, send a message to orchestrator with your findings.

## 2026-09-10T09:01:05Z

**Context**: Jade's AI Humanizer Milestone 1 Implementation
**Content**: You have successfully planned your tasks in progress.md. Please proceed immediately with Task 1 (environment & pyproject.toml), Task 2 (implementing src/humanizer modules), Task 3 (unit tests and benchmarks), and Task 4 (running pytest verification).
**Action**: Execute code implementation, run test verification commands, write handoff.md, and send completion report.
