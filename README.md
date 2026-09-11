# Jade''s AI Humanizer

> **Zero-Backend, Client-Side AI Text Humanizer & REST Daemon**  
> Powered by Google Gemini Flash Lite with minimal prompt token consumption, zero third-party telemetry, offline fallback, and markdown preservation.

---

## Overview

**Jade''s AI Humanizer** is a zero-dependency-backend, completely local Python library, CLI, and standalone REST API daemon. It transforms rigid, repetitive AI-generated text into fluid, natural human writing while preserving document architecture, markdown formatting, code fences, and data tables.

Designed from the ground up for minimal token cost and maximum privacy:
- **100% Client-Side & Local:** Runs directly on your machine. No proxy servers, no third-party tracking, no stored prompts.
- **Minimal Token Consumption:** Uses Google Gemini Flash Lite (`gemini-2.5-flash-lite` / `gemini-2.0-flash-lite`) with ultra-compact prompt engineering (<100 prompt tokens overhead in Budget mode).
- **Offline Deterministic Fallback:** Operates seamlessly even without an API key using local heuristic paraphrasing and guardrail sanitization.
- **Pre-Built Standalone Windows Executable:** Run `dist/humanizer.exe` with a single click—no Python installation required.
- **REST & SSE Streaming Daemon:** Built-in FastAPI/Uvicorn daemon with interactive Swagger UI (`/docs`) and Server-Sent Events (SSE) streaming.

---

## Table of Contents

1. [Features](#features)
2. [Quickstart & Installation](#quickstart--installation)
3. [Standalone Executable (`humanizer.exe`)](#standalone-executable-humanizerexe)
4. [Python Library Usage](#python-library-usage)
   - [Synchronous (`humanize`)](#synchronous-humanize)
   - [Asynchronous (`humanize_async`)](#asynchronous-humanize_async)
   - [Streaming (`humanize_stream` / `humanize_stream_sync`)](#streaming)
5. [CLI Reference](#cli-reference)
6. [REST & Streaming API Reference](#rest--streaming-api-reference)
   - [`GET /health`](#get-health)
   - [`POST /v1/humanize`](#post-v1humanize)
   - [`POST /v1/humanize/stream` (SSE)](#post-v1humanizestream-sse)
7. [Engine Architecture & Quality Guardrails](#engine-architecture--quality-guardrails)
8. [Running Tests](#running-tests)
9. [License](#license)

---

## Features

- **Tiered Humanization Modes:**
  - `budget` *(default)*: Ultra-low token overhead (<100 tokens), compact single-pass prompt, cost-effective for high-volume pipelines.
  - `deep`: Multi-layered rewrite optimizing burstiness variation, perplexity shifts, and natural syntactic rhythms to minimize AI detection.
- **Style Presets & Reading Levels:**
  - Tone presets: `neutral`, `casual`, `academic`, `professional`.
  - Reading levels: `general`, `middle_school`, `high_school`, `college`.
- **Zero-Tolerance AI Buzzword Sanitizer:** Automatically scrubs overused AI clichés (*"delve into"*, *"tapestry of"*, *"testament to"*, *"in conclusion"*, *"moreover"*, *"foster"*, *"multifaceted"*) replacing them with natural synonyms.
- **Grammar & Syntax Post-Processor:** Fixes double spaces, punctuation spacing, capitalization errors, and duplicate words while preserving list and quote indentations.
- **Flesch Readability Scoring:** Automatically calculates and reports Flesch Reading Ease and Flesch-Kincaid Grade Level for before/after comparison.
- **Markdown & Code Invariance:** Safely protects inline code (`` `code` ``), fenced code blocks (```` ``` ```` / `~~~`), math expressions (`$formula$`), URLs/hyperlinks, and GFM tables without token corruption.

---

## Quickstart & Installation

### Option A: From Source / Virtual Environment

```bash
# Clone or navigate to the repository
cd "Jade's AI Humanizer"

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -e .
```

### Option B: Use in Another Python Project (Zero Manual Copying)

You do **not** need to copy any code. You can integrate `humanizer` into any other project using either of these three ways:

#### Method 1: Editable Local Install (Recommended for Local Dev)
In your other project's terminal / virtual environment, run:
```bash
pip install -e "c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer"
```
*Any future updates made to Jade's AI Humanizer are immediately available in your other project without reinstalling.*

#### Method 2: Install Pre-Built Wheel (`.whl`)
A ready-to-install wheel package is available in `dist/`:
```bash
pip install "c:\Users\jacob\OneDrive\Desktop\Coding\Jade's AI Humanizer\dist\humanizer-0.1.0-py3-none-any.whl"
```

#### Method 3: Local REST API / Microservice (Language Agnostic)
Run the local daemon or `dist/humanizer.exe`, and call it from any project (Python, Node.js, Go, etc.) over HTTP:
```python
import requests

res = requests.post("http://127.0.0.1:8000/v1/humanize", json={"text": "Your text here..."})
print(res.json()["humanized_text"])
```

### Option C: Configure Gemini API Key

Set your Google Gemini API key as an environment variable (optional, enables Gemini Flash Lite):

```bash
# Windows PowerShell
$env:GEMINI_API_KEY="your-gemini-api-key"

# Windows Command Prompt
set GEMINI_API_KEY=your-gemini-api-key

# Linux/macOS
export GEMINI_API_KEY="your-gemini-api-key"
```

> **Note:** If no API key is set, the humanizer automatically activates its built-in offline deterministic mock engine, allowing full offline development and testing.

---

## Standalone Executable (`humanizer.exe`)

A standalone Windows executable is pre-compiled in `dist/humanizer.exe`. It bundles Python, FastAPI, Uvicorn, and all dependencies into a single self-contained binary.

- **One-Click Launch:** Double-click `humanizer.exe` in Windows Explorer. It automatically launches the local REST API server on `http://127.0.0.1:8000` and opens the interactive Swagger UI at `/docs`.
- **Custom Port / Host:**
  ```powershell
  dist\humanizer.exe serve --host 127.0.0.1 --port 9000
  ```
- **CLI Humanize Mode:**
  ```powershell
  dist\humanizer.exe humanize "It is crucial to delve into the tapestry of AI."
  ```

To rebuild the executable at any time:
```powershell
.venv\Scripts\python.exe packaging\build_exe.py
```

---

## Python Library Usage

### Synchronous (`humanize`)

```python
from humanizer import Humanizer

client = Humanizer(api_key="your-api-key")  # or reads GEMINI_API_KEY env var

text = """
It is crucial to delve into the intricate tapestry of modern machine learning.
Moreover, this framework serves as a testament to automated efficiency.
"""

result = client.humanize(
    text=text,
    mode="budget",              # "budget" or "deep"
    tone="neutral",             # "neutral", "casual", "academic", "professional"
    reading_level="general",    # "general", "middle_school", "high_school", "college"
    preserve_markdown=True,
)

print("Humanized:\n", result.text)
print("Tokens Used:", result.usage.total_tokens)
print("Flesch Score:", result.readability.flesch_reading_ease)
print("Replaced Clichés:", result.buzzwords_replaced)
```

### Asynchronous (`humanize_async`)

```python
import asyncio
from humanizer import Humanizer

async def main():
    client = Humanizer()
    result = await client.humanize_async(
        text="Furthermore, one must remember that technology is constantly evolving.",
        mode="deep",
        tone="casual"
    )
    print(result.text)

asyncio.run(main())
```

### Streaming

Stream tokens in real time as they are generated:

#### Asynchronous Streaming:
```python
import asyncio
from humanizer import Humanizer

async def main():
    client = Humanizer()
    async for chunk in client.humanize_stream(
        "It is imperative to delve into the underlying mechanics.",
        mode="budget"
    ):
        print(chunk, end="", flush=True)

asyncio.run(main())
```

#### Synchronous Streaming:
```python
from humanizer import Humanizer

client = Humanizer()
for chunk in client.humanize_stream_sync("Delve into the possibilities."):
    print(chunk, end="", flush=True)
```

---

## CLI Reference

The CLI entrypoint is `humanizer`:

```bash
# Check version
humanizer --version

# View all options
humanizer --help

# Start the local REST API daemon (defaults to 127.0.0.1:8000)
humanizer serve --port 8000

# Humanize direct text string
humanizer humanize "It is crucial to delve into the tapestry of AI." --mode deep --tone casual

# Humanize from a markdown file
humanizer humanize -f document.md --mode budget > humanized_document.md

# Pipe through stdin
cat input.txt | humanizer humanize --mode budget
```

---

## REST & Streaming API Reference

Start the local server daemon:
```bash
humanizer serve --port 8000
```
Interactive OpenAPI / Swagger docs are live at `http://127.0.0.1:8000/docs`.

### `GET /health`
Returns daemon health status and active engine configuration.

**Request:**
```bash
curl http://127.0.0.1:8000/health
```

**Response (`200 OK`):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "engine": "gemini-2.5-flash-lite",
  "api_key_configured": true,
  "default_mode": "budget"
}
```

### `POST /v1/humanize`
Rewrites text using specified mode and presets.

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/v1/humanize \
  -H "Content-Type: application/json" \
  -d '{
    "text": "It is crucial to delve into the tapestry of digital innovation.",
    "mode": "budget",
    "tone": "neutral",
    "reading_level": "general",
    "preserve_markdown": true
  }'
```

**Response (`200 OK`):**
```json
{
  "humanized_text": "It's crucial to explore the blend of digital innovation.",
  "original_text": "It is crucial to delve into the tapestry of digital innovation.",
  "mode": "budget",
  "tone": "neutral",
  "reading_level": "general",
  "prompt_tokens": 54,
  "completion_tokens": 9,
  "total_tokens": 63,
  "buzzwords_replaced": ["delve into", "tapestry of"],
  "flesch_reading_ease": 93.0
}
```

### `POST /v1/humanize/stream` (SSE)
Real-time Server-Sent Events (SSE) streaming endpoint.

**Request:**
```bash
curl -N -X POST http://127.0.0.1:8000/v1/humanize/stream \
  -H "Content-Type: application/json" \
  -d '{
    "text": "It is crucial to delve into modern software architecture.",
    "mode": "budget"
  }'
```

**SSE Output Stream:**
```
data: {"chunk": "It's"}

data: {"chunk": " crucial"}

data: {"chunk": " to"}

data: {"chunk": " explore"}

data: {"chunk": " modern"}

data: {"chunk": " software"}

data: {"chunk": " architecture."}

data: [DONE]
```

---

## Engine Architecture & Quality Guardrails

```
Raw Input Text
      │
      ▼
┌───────────────────────────────────────┐
│ 1. Markdown & Token Masking Parser    │
│    - Extracts & isolates code blocks  │
│    - Masks URLs, Math ($), GFM Tables │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ 2. Semantic Chunking                  │
│    - Splits on paragraph boundaries   │
│    - Handles oversized paragraphs     │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ 3. Gemini Flash Lite Engine           │
│    - Compact prompt (<70 tokens)      │
│    - Budget / Deep Paraphraser        │
│    - Offline Mock Fallback Engine     │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ 4. Quality & Vocabulary Guardrails    │
│    - 0-Tolerance AI Buzzword Filter   │
│    - Punctuation & Spacing Sanitizer  │
│    - Readability Scoring Engine       │
└──────────────────┬────────────────────┘
                   │
                   ▼
┌───────────────────────────────────────┐
│ 5. Reconstruction & Unmasking         │
│    - Reintegrates untouched blocks    │
│    - Restores exact indentation       │
└──────────────────┬────────────────────┘
                   │
                   ▼
Humanized Output Text
```

---

## Running Tests

The test suite includes unit tests, end-to-end integration tests, adversarial stress tests, and token overhead benchmarks:

```bash
# Run all 285 tests
.venv\Scripts\pytest tests/

# Run benchmark tests
.venv\Scripts\pytest tests/benchmarks/

# Run adversarial stress tests
.venv\Scripts\pytest tests/unit/test_markdown_stress.py
```

---

## License

MIT License. Designed and built for seamless integration into any project.
