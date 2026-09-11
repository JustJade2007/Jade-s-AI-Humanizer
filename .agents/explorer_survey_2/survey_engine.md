# Technical Survey: Token-Minimized Humanization Engine & Gemini API Integration

**Agent:** Explorer 2 (`teamwork_preview_explorer`)  
**Working Directory:** `.agents/explorer_survey_2`  
**Date:** 2026-09-10  
**Target Requirement:** Requirement R2 (Token-Minimized Humanization Engine) & Requirement R1 (Gemini Integration)

---

## 1. Executive Summary

Jade's AI Humanizer requires a local, zero-backend Python engine capable of transforming synthetic, predictable AI-generated prose into authentic, human-sounding text. To achieve this cost-effectively and evade AI detection, the engine must leverage Google's current lightweight model family (**Gemini Flash Lite**) via the modern `google-genai` SDK.

This survey establishes the complete technical blueprint for:
1. **Gemini Flash Lite API Integration**: Native sync, async, and streaming patterns using `google-genai`.
2. **Budget Mode**: A single-pass, hyper-compact system instruction guaranteeing **< 100 prompt tokens overhead** per request while delivering burstiness and naturalness.
3. **Deep Mode**: A multi-layered paraphrasing pipeline targeting structural rhythm variation, idiom injection, and syntactic cadence shifts.
4. **Style Presets**: Standardized implementations for `tone` (`neutral`, `casual`, `academic`, `professional`) and `reading_level` (Flesch-Kincaid mapped).
5. **Quality Guardrails**: A zero-dependency local verification suite consisting of an automated **0-tolerance AI buzzword audit** and **heuristic syntax/grammar sanitization**.

---

## 2. Gemini API & `google-genai` SDK Integration Specifications

### 2.1 SDK Selection and Packaging
- **Package**: `google-genai` (version >= 0.1.1, latest release).
- **Deprecated SDKs**: Do NOT use `google-generativeai` or `@google/generative-ai` (officially deprecated legacy libraries).
- **Import Pattern**:
  ```python
  from google import genai
  from google.genai import types
  ```

### 2.2 Client Initialization
The client must support explicit API key injection or automatic resolution from `os.environ["GEMINI_API_KEY"]`:
```python
import os
from typing import Optional
from google import genai

def create_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    resolved_key = api_key or os.getenv("GEMINI_API_KEY")
    if not resolved_key:
        raise ValueError(
            "Gemini API key must be provided explicitly or set in GEMINI_API_KEY environment variable."
        )
    return genai.Client(api_key=resolved_key)
```

### 2.3 Recommended Models & Model ID Strategy
Google Gemini's model line offers Flash Lite models optimized for high-throughput, low-latency, and minimal cost:
- **Primary Model**: `gemini-2.5-flash-lite` (current generation high-throughput Flash Lite)
- **Secondary / Fallback Model**: `gemini-2.0-flash-lite` (widely deployed Flash Lite endpoint)
- **Alternative High-Power Model**: `gemini-2.5-flash` (balanced reasoning and speed)

**Configuration**: The engine must allow setting the model via constructor argument or `GEMINI_MODEL` environment variable, defaulting to `gemini-2.5-flash-lite`.

### 2.4 Invocation Patterns

#### 1. Synchronous Invocation (Non-Streaming)
```python
def generate_sync(
    client: genai.Client,
    model: str,
    prompt: str,
    system_instruction: str,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
) -> tuple[str, int, int]:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    usage = response.usage_metadata
    prompt_tokens = usage.prompt_token_count if usage else 0
    candidate_tokens = usage.candidates_token_count if usage else 0
    return response.text or "", prompt_tokens, candidate_tokens
```

#### 2. Asynchronous Invocation (Non-Streaming)
```python
async def generate_async(
    client: genai.Client,
    model: str,
    prompt: str,
    system_instruction: str,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
) -> tuple[str, int, int]:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )
    response = await client.aio.models.generate_content(
        model=model,
        contents=prompt,
        config=config,
    )
    usage = response.usage_metadata
    prompt_tokens = usage.prompt_token_count if usage else 0
    candidate_tokens = usage.candidates_token_count if usage else 0
    return response.text or "", prompt_tokens, candidate_tokens
```

#### 3. Synchronous Streaming
```python
from typing import Iterator

def generate_stream_sync(
    client: genai.Client,
    model: str,
    prompt: str,
    system_instruction: str,
    temperature: float = 0.7,
) -> Iterator[str]:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=config,
    ):
        if chunk.text:
            yield chunk.text
```

#### 4. Asynchronous Streaming (for FastAPI / SSE)
*Crucial SDK Detail*: `await client.aio.models.generate_content_stream(...)` returns the async generator object:
```python
from typing import AsyncIterator

async def generate_stream_async(
    client: genai.Client,
    model: str,
    prompt: str,
    system_instruction: str,
    temperature: float = 0.7,
) -> AsyncIterator[str]:
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=temperature,
    )
    stream = await client.aio.models.generate_content_stream(
        model=model,
        contents=prompt,
        config=config,
    )
    async for chunk in stream:
        if chunk.text:
            yield chunk.text
```

### 2.5 Token Counting & Measurement
The SDK provides `client.models.count_tokens`:
```python
def count_tokens(client: genai.Client, model: str, text: str) -> int:
    res = client.models.count_tokens(model=model, contents=text)
    return res.total_tokens
```
In tests and production, prompt token overhead is formally verified as:
$$\text{Overhead Tokens} = \text{response.usage\_metadata.prompt\_token\_count} - \text{count\_tokens}(input\_text)$$

---

## 3. Budget Mode: Token-Minimized Engine (<100 Prompt Tokens Overhead)

### 3.1 The Overhead Constraint
Requirement R2 & Acceptance Criteria dictate:
> *Automated benchmark test demonstrates `budget` mode operates under strict token overhead thresholds (<100 prompt tokens overhead per request).*

Prompt token overhead is strictly defined as all tokens sent to the model minus the tokens of the raw input text:
$$\text{Overhead} = \text{Tokens}(\text{System Instruction}) + \text{Tokens}(\text{Framing / Markers})$$

### 3.2 System Prompt Design for Budget Mode
To guarantee the overhead remains well under 100 tokens (targeting 40–55 tokens, giving a >45% safety margin), the system instruction must be direct, dense, and imperative:

```text
Rewrite text to sound naturally human. Vary sentence lengths, use active voice, eliminate AI buzzwords (e.g. delve, tapestry, moreover, testament, pivotal), and preserve facts, markdown, and code blocks untouched. Output only the rewritten text.
```

**Token & Word Analysis:**
- **Word count**: 35 words.
- **Estimated Gemini tokens**: ~42 to 46 tokens.
- **Tone/Reading Level modifier**: Adds 4 to 8 words (e.g., `Tone: casual. Reading level: high school.` -> ~7 tokens).
- **Total System Instruction Tokens**: **~49 to 53 tokens**.
- **User Prompt Formatting**: Sending the raw text directly in `contents=text` adds **0 overhead tokens** (no wrapper boilerplate).
- **Total Request Prompt Overhead**: **~50 tokens**, passing the `< 100 tokens` threshold with flying colors.

### 3.3 Preserving Naturalness Under Ultra-Compact Constraints
Why this compact prompt works:
1. **Rhythm directive ("Vary sentence lengths")**: AI text suffers from uniform sentence lengths (~18–22 words per sentence). Instructing length variation triggers natural human *burstiness*.
2. **Grammatical mode ("Use active voice")**: Dislodges passive, impersonal corporate phrasing.
3. **Negative constraint ("eliminate AI buzzwords")**: Seeds the model's output distribution away from top statistical attractors.
4. **Structural constraint ("preserve facts, markdown, and code blocks untouched")**: Ensures non-destructive transformation.
5. **Output framing ("Output only the rewritten text")**: Prevents token-wasting preamble ("Sure, here is your rewritten text:").

### 3.4 Generation Parameters for Budget Mode
- `temperature`: `0.75` (high enough to avoid predictable n-grams, low enough to preserve factual precision).
- `top_p`: `0.95`.
- `presence_penalty` / `frequency_penalty`: if supported by the model endpoint, slight positive value (`0.1`) discourages repetitive phrase structures.

---

## 4. Deep Mode: Multi-Layered Paraphrasing Engine

`deep` mode is designed for maximum naturalness and detection evasion when token minimization is secondary to undetectable human cadence.

### 4.1 Theory of AI Detection Evasion
AI detectors (GPTZero, Turnitin, CopyLeaks, Originality.ai) measure two primary statistical indicators:
1. **Perplexity**: How predictable each subsequent word is given previous tokens. AI models pick high-probability tokens. Human writers use diverse vocabulary, metaphors, and non-linear transitions.
2. **Burstiness**: The variation in sentence length, syntax, and rhythm. AI models produce uniform, mid-length sentences. Humans oscillate between 3-word fragments and 40-word multi-clause sentences.

### 4.2 Deep Mode Architecture: Two Pipeline Approaches

The engine can support two operational variants of `deep` mode:
1. **Single-Pass Deep Paraphrase** (High-speed deep mode, compatible with SSE streaming): Uses a comprehensive multi-layered cognitive prompt.
2. **Two-Pass Sequential Pipeline** (Maximum detection evasion):
   - **Pass 1 (Syntactic Cadence & Structural Inversion)**: Deconstructs the rigid AI syntax, breaks symmetric lists, splits run-ons, joins fragments, and randomizes sentence rhythm.
   - **Pass 2 (Voice Calibration & Idiom Injection)**: Applies style presets, injects natural vernacular/idioms, checks semantic preservation, and normalizes flow.

### 4.3 Deep Mode Master Prompt (Single-Pass & Streaming)
```text
You are an expert human editor and prose stylist. Rewrite the input text to completely eliminate all statistical and stylistic markers of AI generation while preserving 100% of the core factual meaning, technical terms, markdown structure, and code blocks.

Apply these layered transformations:
1. Structural Cadence & Burstiness: Break monotonous sentence structures. Alternate between short, punchy sentences (3-7 words) and longer, rhythmic sentences (20-35 words). Invert clauses and avoid robotic tripartite patterns.
2. Natural Phrasing & Idioms: Replace sterile, synthetic expressions with authentic human idioms, natural conversational transitions, and active verbs.
3. Vocabulary Purification: Strictly purge all AI clichés, including 'delve', 'tapestry', 'beacon', 'multifaceted', 'pivotal', 'testament', 'plethora', 'moreover', 'furthermore', 'in summary', and 'it is crucial to remember'.
4. Tone & Voice Alignment: {tone_instruction}
5. Reading Level: {reading_level_instruction}

Output only the humanized text with no preamble, metadata, or closing commentary.
```

### 4.4 Two-Pass Pipeline Implementation
```python
async def humanize_deep_multipass(
    client: genai.Client,
    model: str,
    text: str,
    tone: str,
    reading_level: str,
) -> str:
    # Pass 1: Structural & Rhythm Restructuring
    pass1_system = (
        "Deconstruct and restructure the following text. Radically alter sentence "
        "rhythms, invert clauses, and vary sentence lengths between very short and "
        "complex. Retain all facts, markdown, and code blocks untouched."
    )
    draft, _, _ = await generate_async(
        client, model, text, pass1_system, temperature=0.85
    )

    # Pass 2: Voice, Idiom, and Preset Calibration
    pass2_system = (
        f"Polish this draft into fluent, authentic human writing. "
        f"Apply {tone} tone and {reading_level} reading level. "
        f"Inject natural idioms and eliminate any remaining AI clichés. "
        f"Output only the final text."
    )
    final_text, _, _ = await generate_async(
        client, model, draft, pass2_system, temperature=0.7
    )

    return final_text
```

---

## 5. Style Presets Specification

### 5.1 Tone Configurations

| Preset | Target Persona | Prompt Directive | Stylistic Markers |
| :--- | :--- | :--- | :--- |
| `neutral` *(default)* | Balanced, clear communicator | *"Maintain a balanced, objective, and clear human voice. Avoid both stiff corporate jargon and informal slang."* | Clean active voice, direct explanations, accessible phrasing. |
| `casual` | Friendly peer or colleague | *"Adopt a relaxed, conversational tone. Use natural contractions (e.g. don't, it's, you'll), lively sentence openings, and warm, relatable phrasing."* | Contractions, conversational rhetorical questions, punchy transitions (`honestly`, `plus`, `anyway`). |
| `academic` | Scholarly researcher / essayist | *"Use an intellectually rigorous, evidence-oriented tone. Prioritize analytical precision and clear logical flow while strictly avoiding AI fluff ('delve', 'tapestry')."* | Precise domain terminology, passive-to-active balance, rigorous qualifications (`indicates`, `demonstrates`). |
| `professional` | Executive / business practitioner | *"Adopt a polished, executive business tone. Be direct, concise, and action-oriented. Eliminate empty buzzwords ('synergize', 'game-changer')."* | High information density, decisive action verbs, respectful and efficient phrasing. |

### 5.2 Reading Level Configurations

| Preset | Target Grade | Flesch-Kincaid Grade Level (FKGL) | Prompt Directive |
| :--- | :--- | :--- | :--- |
| `middle_school` | Grades 6–8 | 6.0 – 8.9 | *"Write at an accessible middle-school reading level. Use common vocabulary, short sentences, and straightforward concepts."* |
| `high_school` | Grades 9–12 | 9.0 – 12.9 | *"Write at a standard high-school reading level with balanced vocabulary and varied sentence complexity."* |
| `college` | Undergraduate | 13.0 – 16.0 | *"Write at an advanced collegiate reading level using sophisticated vocabulary and nuanced multi-clause structures."* |
| `general` *(default)* | Broad Audience | 7.5 – 9.5 | *"Write for a general public audience. Clear, engaging, and easily understood without requiring domain expertise."* |

### 5.3 Local Zero-Dependency Readability Calculator
To evaluate output text without heavy third-party packages, the library will include a pure-Python Flesch-Kincaid calculator:
```python
import re

def count_syllables(word: str) -> int:
    word = word.lower().strip(".:;?!")
    if len(word) <= 3:
        return 1
    word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
    word = re.sub(r'^y', '', word)
    matches = re.findall(r'[aeiouy]{1,2}', word)
    return max(1, len(matches))

def calculate_readability(text: str) -> dict[str, float]:
    # Strip markdown and code blocks before calculating
    clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
    sentences = [s for s in re.split(r'[.!?]+', clean_text) if s.strip()]
    
    if not words or not sentences:
        return {"fkgl": 0.0, "fre": 100.0}
    
    total_words = len(words)
    total_sentences = len(sentences)
    total_syllables = sum(count_syllables(w) for w in words)
    
    # Flesch-Kincaid Grade Level formula
    fkgl = 0.39 * (total_words / total_sentences) + 11.8 * (total_syllables / total_words) - 15.59
    # Flesch Reading Ease formula
    fre = 206.835 - 1.015 * (total_words / total_sentences) - 84.6 * (total_syllables / total_words)
    
    return {"fkgl": round(fkgl, 1), "fre": round(fre, 1)}
```

---

## 6. Quality & Vocabulary Guardrails Engine

### 6.1 Banned AI Buzzwords Audit (0 Tolerance)
AI models reliably generate a specific vocabulary of rhetorical crutches. The library enforces an automated scan and post-processing sanitizer to guarantee **0 occurrences**.

#### Comprehensive Banned Terms Catalog
```python
BANNED_AI_TERMS: list[str] = [
    # Verbs / Verb Phrases
    r"\bdelv(?:e|es|ed|ing)(?:\s+into)?\b",
    r"\bshowcas(?:e|es|ed|ing)\b",
    r"\bunderscor(?:e|es|ed|ing)\b",
    r"\bharness(?:es|ed|ing)?\b",
    r"\bfoster(?:s|ed|ing)?\b",
    r"\bgarner(?:s|ed|ing)?\b",
    r"\billuminat(?:e|es|ed|ing)\b",
    r"\bshed(?:s)?\s+light\s+on\b",
    r"\bserves?\s+as\s+a\s+(?:testament|reminder|beacon)\b",
    
    # Nouns / Metaphors
    r"\btapestr(?:y|ies)\b",
    r"\bbeacon(?:s)?\b",
    r"\btestament(?:s)?\b",
    r"\bplethora\b",
    r"\bmyriad(?:\s+of)?\b",
    r"\brealm(?:s)?\b",
    r"\bcrucible\b",
    r"\bcornerstone\b",
    r"\blinchpin\b",
    r"\bsymphon(?:y|ies)\b",
    r"\binterplay\b",
    r"\bparadigm\s+shift\b",
    r"\bgame[- ]changer\b",
    
    # Adjectives / Adverbs
    r"\bmultifaceted\b",
    r"\bpivotal\b",
    r"\bquintessential\b",
    r"\bseamless(?:ly)?\b",
    r"\bmeticulous(?:ly)?\b",
    r"\bbespoke\b",
    r"\btransformative\b",
    r"\bvibrant\b",
    r"\bbustling\b",
    r"\bparamount\b",
    r"\binvaluable\b",
    r"\bgroundbreaking\b",
    r"\bnascent\b",
    r"\binextricably\b",
    
    # Formulaic Transitions
    r"\bmoreover\b",
    r"\bfurthermore\b",
    r"\bin\s+summary\b",
    r"\bin\s+conclusion\b",
    r"\bto\s+sum\s+up\b",
    r"\bit\s+is\s+worth\s+noting\s+that\b",
    r"\bit\s+is\s+important\s+to\s+remember\s+that\b",
    r"\bby\s+and\s+large\b",
]
```

#### Local Heuristic Replacement Map
If an LLM produces a banned word despite prompting, the post-processor surgically replaces it with contextual, human-natural alternatives before returning to the caller:
```python
REPLACEMENT_RULES: dict[str, str] = {
    r"\bdelve\s+into\b": "explore",
    r"\bdelves\s+into\b": "explores",
    r"\bdelving\s+into\b": "exploring",
    r"\bdelve\b": "dig",
    r"\btapestry\s+of\b": "rich mix of",
    r"\btapestry\b": "fabric",
    r"\bmoreover,\b": "also,",
    r"\bmoreover\b": "plus",
    r"\bfurthermore,\b": "what's more,",
    r"\bfurthermore\b": "in addition",
    r"\bin\s+summary,\b": "overall,",
    r"\bin\s+conclusion,\b": "in the end,",
    r"\btestament\s+to\b": "proof of",
    r"\bmultifaceted\b": "complex",
    r"\bplethora\s+of\b": "wide variety of",
    r"\bplethora\b": "wealth",
    r"\bpivotal\b": "critical",
    r"\bbeacon\s+of\b": "symbol of",
    r"\bseamlessly\b": "smoothly",
    r"\bmeticulously\b": "carefully",
}
```

#### Verification Function
```python
def audit_vocabulary(text: str) -> list[str]:
    """Returns all banned AI buzzwords found in the text (case-insensitive)."""
    violations = []
    for pattern in BANNED_AI_TERMS:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        if matches:
            violations.extend(matches)
    return violations
```

### 6.2 Automated Post-Processing Grammar Verification
LLM rewrites and streaming chunking can occasionally produce artifacts. A local grammar verification pass guarantees clean syntax and punctuation without requiring heavy external runtimes (e.g. Java for LanguageTool).

#### Guardrail Verification Checks
1. **Unmatched Quote / Bracket Balance**: Verifies that quotes `"` and parentheses `()` opened within paragraphs are properly closed (while ignoring code blocks).
2. **Punctuation Spacing**: Detects and fixes improper spacing preceding punctuation (e.g., `word , word` -> `word, word`).
3. **Double Punctuation & Ellipsis Protection**: Normalizes `..` into `.` or `...`, removes duplicate commas `,,`.
4. **Sentence Capitalization**: Verifies that every sentence following terminal punctuation (`.`, `!`, `?`) begins with an uppercase letter.
5. **Reduplication / Stutter**: Detects accidental duplicate words (e.g., `the the`, `with with`).
6. **Code Block Integrity**: Verifies that all triple backticks (```` ``` ````) are balanced and intact.

#### Syntax Sanitizer & Verifier Implementation
```python
class GrammarVerificationResult:
    def __init__(self, is_valid: bool, issues: list[str], repaired_text: str):
        self.is_valid = is_valid
        self.issues = issues
        self.repaired_text = repaired_text

def sanitize_and_verify_grammar(text: str) -> GrammarVerificationResult:
    issues = []
    repaired = text
    
    # 1. Check code block balance
    backticks = repaired.count("```")
    if backticks % 2 != 0:
        issues.append(f"Unmatched markdown code fence: found {backticks} backtick sets.")
        repaired += "\n```\n"

    # 2. Fix space before punctuation: 'word , word' -> 'word, word'
    space_punct_pattern = r'\s+([,.:;?!])'
    if re.search(space_punct_pattern, repaired):
        issues.append("Found extraneous whitespace before punctuation marks.")
        repaired = re.sub(space_punct_pattern, r'\1', repaired)

    # 3. Fix double commas or misplaced punctuation
    if re.search(r',,+', repaired):
        issues.append("Found duplicate commas.")
        repaired = re.sub(r',,+', ',', repaired)
        
    # 4. Fix accidental word reduplication: 'the the' -> 'the'
    stutter_pattern = r'\b([a-zA-Z]{2,})\s+\1\b'
    if re.search(stutter_pattern, repaired, flags=re.IGNORECASE):
        issues.append("Found accidental word reduplication (stutter).")
        repaired = re.sub(stutter_pattern, r'\1', repaired, flags=re.IGNORECASE)

    # 5. Verify sentence capitalization
    sentence_cap_pattern = r'([.!?]\s+)([a-z])'
    if re.search(sentence_cap_pattern, repaired):
        issues.append("Found lowercase character starting a sentence.")
        repaired = re.sub(sentence_cap_pattern, lambda m: m.group(1) + m.group(2).upper(), repaired)

    is_valid = len(issues) == 0
    return GrammarVerificationResult(is_valid=is_valid, issues=issues, repaired_text=repaired)
```

---

## 7. Python Library Class Architecture & Interface Contracts

To satisfy Requirement R1 (`from humanizer import Humanizer`) and R2, the core module will be structured with clean, type-hinted classes.

### 7.1 Proposed Package Hierarchy
```
humanizer/
├── __init__.py          # Exports Humanizer, HumanizeConfig, Tone, Mode, ReadingLevel
├── client.py            # Gemini API wrapper (sync, async, streaming, token counting)
├── engine.py            # Core Humanizer pipeline (prompt assembly, budget/deep modes)
├── prompts.py           # Compact budget templates, deep mode templates, style directives
├── guardrails.py        # Vocabulary audit, regex replacements, grammar verification
├── readability.py      # Zero-dependency Flesch-Kincaid readability scoring
└── exceptions.py       # HumanizerError, AuthenticationError, TokenLimitError
```

### 7.2 Core Class Contract (`Humanizer`)
```python
from typing import Optional, Iterator, AsyncIterator, Union
from enum import Enum
from dataclasses import dataclass

class Mode(str, Enum):
    BUDGET = "budget"
    DEEP = "deep"

class Tone(str, Enum):
    NEUTRAL = "neutral"
    CASUAL = "casual"
    ACADEMIC = "academic"
    PROFESSIONAL = "professional"

class ReadingLevel(str, Enum):
    GENERAL = "general"
    MIDDLE_SCHOOL = "middle_school"
    HIGH_SCHOOL = "high_school"
    COLLEGE = "college"

@dataclass
class UsageMetadata:
    prompt_tokens: int
    candidate_tokens: int
    total_tokens: int
    prompt_overhead_tokens: int

@dataclass
class HumanizeResult:
    text: str
    mode: Mode
    tone: Tone
    reading_level: ReadingLevel
    usage: UsageMetadata
    readability_scores: dict[str, float]
    banned_words_detected: list[str]
    grammar_repaired: bool

    def __str__(self) -> str:
        return self.text

class Humanizer:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash-lite",
        default_mode: Union[Mode, str] = Mode.BUDGET,
        default_tone: Union[Tone, str] = Tone.NEUTRAL,
        default_reading_level: Union[ReadingLevel, str] = ReadingLevel.GENERAL,
    ):
        ...

    def humanize(
        self,
        text: str,
        mode: Optional[Union[Mode, str]] = None,
        tone: Optional[Union[Tone, str]] = None,
        reading_level: Optional[Union[ReadingLevel, str]] = None,
    ) -> HumanizeResult:
        """Synchronously humanizes the input text."""
        ...

    async def humanize_async(
        self,
        text: str,
        mode: Optional[Union[Mode, str]] = None,
        tone: Optional[Union[Tone, str]] = None,
        reading_level: Optional[Union[ReadingLevel, str]] = None,
    ) -> HumanizeResult:
        """Asynchronously humanizes the input text."""
        ...

    def humanize_stream(
        self,
        text: str,
        mode: Optional[Union[Mode, str]] = None,
        tone: Optional[Union[Tone, str]] = None,
        reading_level: Optional[Union[ReadingLevel, str]] = None,
    ) -> Iterator[str]:
        """Synchronously streams humanized text chunks."""
        ...

    async def humanize_stream_async(
        self,
        text: str,
        mode: Optional[Union[Mode, str]] = None,
        tone: Optional[Union[Tone, str]] = None,
        reading_level: Optional[Union[ReadingLevel, str]] = None,
    ) -> AsyncIterator[str]:
        """Asynchronously streams humanized text chunks (for SSE / FastAPI)."""
        ...
```

---

## 8. Offline Testing & Mocking Strategy

Because local test runners and CI environments may execute without live `GEMINI_API_KEY` credentials or active network access, the implementation must support seamless testing:
1. **Mock Gemini Client**: A lightweight mock client implementing the exact same `generate_content`, `generate_content_stream`, and `count_tokens` interfaces, returning realistic token counts and text responses.
2. **Deterministic Token Simulation**: A mock tokenizer that calculates tokens accurately (e.g. 1 token per 4 chars or regex word tokenization) so that tests for `< 100 prompt token overhead` run deterministically in milliseconds.
3. **Guardrail Unit Tests**: 100% of the vocabulary audit (`audit_vocabulary`) and grammar sanitization (`sanitize_and_verify_grammar`) functions are pure local algorithms with zero network calls, enabling exhaustive testing of edge cases (unmatched fences, buzzword permutations, stutter words).

---

## 9. Next Steps & Handoff Recommendations
- Provide this specification to the Orchestrator to integrate with Explorer 1 (environment scan) and Explorer 3 (chunking & packaging).
- When Milestone 1 (Core Humanizer Engine) begins, implement `humanizer/guardrails.py`, `humanizer/prompts.py`, `humanizer/client.py`, and `humanizer/engine.py` following the exact contracts laid out in this survey.
