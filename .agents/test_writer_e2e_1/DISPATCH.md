## 2026-09-10T08:58:05Z
You are a Test Writer (`teamwork_preview_test_writer`) leading the E2E Testing Track for Jade's AI Humanizer.
Your working directory is:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\test_writer_e2e_1

MANDATORY FIRST STEP: Read the authoritative requirements in:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\ORIGINAL_REQUEST.md

Also read the architecture and specifications in:
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\PROJECT.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_2\survey_engine.md
c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\explorer_survey_3\survey_architecture_packaging.md

Your Mission:
Design and build the comprehensive opaque-box E2E test suite covering EVERY feature in PROJECT.md § Feature Inventory (F1 through F12) using the 4-tier methodology:
- Tier 1: Feature Coverage (>=5 test cases per feature covering happy paths and representative inputs in isolation)
- Tier 2: Boundary & Corner Cases (>=5 test cases per feature covering empty inputs, max-size text, zero/negative, punctuation extremes, malformed markdown, unclosed code fences, unicode, special chars)
- Tier 3: Cross-Feature Combinations (pairwise interactions: budget+markdown, deep+tables, tone+reading_level+streaming, API daemon+SSE+chunking)
- Tier 4: Real-World Application Scenarios (>=5 realistic application scenarios: blog post humanization, technical paper with code blocks and formulas, customer support email, marketing pitch rewrite, multi-page article)

Exclusive File Ownership:
You exclusively own:
- `tests/e2e/` (e.g. `tests/e2e/conftest.py`, `tests/e2e/test_tier1_features.py`, `tests/e2e/test_tier2_boundaries.py`, `tests/e2e/test_tier3_combinations.py`, `tests/e2e/test_tier4_scenarios.py`)
- `TEST_INFRA.md` at project root
- `TEST_READY.md` at project root

Guidelines:
1. Tests must be opaque-box, testing the public interfaces: `from humanizer import Humanizer`, CLI commands (`humanizer serve`), and HTTP endpoints (`POST /v1/humanize`, `GET /health`, `POST /v1/humanize/stream`).
2. Include offline mock fixtures / responses so the entire test suite can run deterministically without requiring a live paid Gemini API key in CI/test environments, while still supporting real API keys if `GEMINI_API_KEY` is present.
3. Once all test files are written and verified, create `TEST_INFRA.md` and `TEST_READY.md` per the templates in `PROJECT.md`.
4. Run tests with pytest to verify syntax and test discovery.
5. Write your handoff report to `c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\.agents\test_writer_e2e_1\handoff.md`.
When done, send a message to orchestrator with your findings.

## 2026-09-10T09:01:08Z
**Context**: Jade's AI Humanizer E2E Testing Track
**Content**: You have initialized your environment. Please proceed immediately to author the 4-tier opaque-box E2E test suite in tests/e2e/ covering all features F1-F12, publish TEST_INFRA.md and TEST_READY.md, verify test syntax with pytest, and deliver your handoff report.
**Action**: Implement test suite in tests/e2e/, write TEST_INFRA.md and TEST_READY.md, write handoff.md, and send completion report.
