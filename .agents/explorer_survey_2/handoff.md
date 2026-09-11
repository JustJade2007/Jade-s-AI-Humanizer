# Handoff Report — Explorer Survey 2 (Token-Minimized Engine & Gemini Integration)

## 1. Observation
- **Authoritative Requirements**: In `.agents/ORIGINAL_REQUEST.md:19-27`, Requirement R2 defines:
  - `budget` (default): Single-pass minimal token rewrite utilizing compact system instructions and local rule-based heuristics to minimize prompt token overhead (<100 prompt tokens overhead per request, `.agents/ORIGINAL_REQUEST.md:45`).
  - `deep`: Multi-layered paraphrasing for maximum naturalness and detection evasion.
  - Style Presets: Configurable `tone` (`neutral`, `casual`, `academic`, `professional`) and `reading_level`.
  - Quality Guardrails: Automated post-processing grammar verification and 0 banned AI buzzwords (`delve`, `tapestry`, `in summary`, `moreover`, etc.).
- **Gemini SDK Status**: MCP documentation for `google-genai` confirms:
  - Package is `google-genai` (deprecated: `google-generativeai`).
  - Import is `from google import genai; from google.genai import types`.
  - Sync generation: `client.models.generate_content(model=..., contents=..., config=types.GenerateContentConfig(system_instruction=...))`.
  - Async generation: `await client.aio.models.generate_content(...)`.
  - Sync streaming: `client.models.generate_content_stream(...)`.
  - Async streaming: `await client.aio.models.generate_content_stream(...)` which yields an async iterator.
  - Token counting: `client.models.count_tokens(model=..., contents=...)` returning `total_tokens`.
  - Usage metadata on response: `response.usage_metadata.prompt_token_count` and `candidates_token_count`.
- **Active Model Codes**: Upstream documentation confirms current Flash Lite models: `gemini-2.5-flash-lite` (primary high-throughput) and `gemini-2.0-flash-lite` (compatible alternative).
- **Environment**: Global python interpreter is Python 3.14.2; packages `requests`, `pyinstaller`, `Markdown`, `pypdf`, `python-docx` are present. Dependencies `google-genai`, `fastapi`, `uvicorn` will be required for the project.

## 2. Logic Chain
1. **Prompt Overhead Constraint**:
   - Prompt overhead is formally defined as: $\text{Prompt Tokens (with system instruction)} - \text{Tokens (raw user text)}$.
   - If user text is placed directly in `contents=text` with zero formatting wrappers, the only prompt overhead is the system instruction.
   - The designed compact budget instruction is 35 words (~45 tokens): `"Rewrite text to sound naturally human. Vary sentence lengths, use active voice, eliminate AI buzzwords (e.g. delve, tapestry, moreover, testament, pivotal), and preserve facts, markdown, and code blocks untouched. Output only the rewritten text."`
   - Adding tone and reading level presets introduces 4 to 8 words (~7 tokens).
   - Total overhead is ~52 tokens, which is strictly less than the 100-token ceiling specified in Acceptance Criteria `.agents/ORIGINAL_REQUEST.md:45`.
2. **Deep Mode Detection Evasion**:
   - AI detectors rely on n-gram predictability (low perplexity) and uniform sentence length (low burstiness).
   - Deep mode solves this through explicit multi-layered directives (varying sentence length between 3 and 35 words, inverting clauses, injecting natural idioms and contractions, purging all robotic connectors like "moreover" or "in summary").
   - Can operate in single-pass (streaming friendly) or two-pass sequential pipeline (maximum evasion).
3. **Style & Reading Level Presets**:
   - Four distinct tones (`neutral`, `casual`, `academic`, `professional`) map to concise persona instructions.
   - Four reading levels (`middle_school`, `high_school`, `college`, `general`) are validated with a zero-dependency pure-Python Flesch-Kincaid calculator.
4. **Automated Quality & Vocabulary Guardrails**:
   - 0-tolerance buzzword audit: A compiled regex pattern of 40+ high-frequency AI words/phrases (`delve`, `tapestry`, `beacon`, `testament`, `multifaceted`, `plethora`, etc.) coupled with local heuristic replacements ensures 0 occurrences even if an LLM slips up.
   - Automated grammar verification: Checks for unmatched code fences, broken punctuation spacing (`word , word`), duplicate commas, word stutters (`the the`), and capitalizes sentence beginnings.

## 3. Caveats
- `google-genai` SDK is not yet installed in the global Python 3.14 environment. It must be installed or managed according to project dependency practices during implementation.
- Testing against live Gemini API endpoints requires a valid `GEMINI_API_KEY`. A comprehensive local mock client and token simulator has been specified in `survey_engine.md:Section 8` to allow 100% test coverage in offline/CI environments.
- In `deep` mode, if a two-pass pipeline is selected, it will consume approximately 2x latency and tokens relative to single-pass. Single-pass deep mode is recommended when SSE streaming is active.

## 4. Conclusion
Requirement R2 is fully feasible with high precision, minimal token expenditure, and zero third-party dependencies outside `google-genai`. All prompt templates, SDK invocation patterns, token budgets, style matrices, and guardrail algorithms are formally documented and ready for implementation in Milestone 1.

## 5. Verification Method
1. Inspect `.agents/explorer_survey_2/survey_engine.md` for full implementation details, prompt text, token budgets, and class interfaces.
2. Verify token budget calculation:
   - Word count of budget prompt is 35 words.
   - At standard English BPE tokenization (~1.3 tokens/word), 35 words equates to ~45 tokens, leaving >45 tokens buffer under the 100-token limit.
3. Verify guardrails logic:
   - Run Python regex checks on sample text containing "delve into the rich tapestry" to verify both detection in `audit_vocabulary` and substitution to "explore the rich mix of".
