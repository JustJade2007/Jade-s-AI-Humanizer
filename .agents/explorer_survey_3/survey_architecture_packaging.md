# Survey: Architecture, Markdown Chunking, Daemon, and Packaging

**Author:** Explorer Survey 3 (`teamwork_preview_explorer`)  
**Date:** 2026-09-10  
**Scope:** Requirements R1 (CLI, Daemon, SSE, Packaging), R3 (Markdown/Structural Chunking), R4 (Documentation), and User Global Rules.

---

## 1. Executive Summary

Jade's AI Humanizer is engineered as a **zero-backend, client-side/local Python text humanizer library, CLI, and standalone REST API daemon** powered by Gemini Flash Lite. To satisfy the project requirements and user global rules, the architecture must balance three key qualities:
1. **Structural Invariance:** Documents (articles, technical documentation, academic papers) must be humanized without corrupting Markdown formatting, lists, tables, links, inline code, or fenced code blocks.
2. **Modular Layering:** A clean separation between the in-process Python SDK (`from humanizer import Humanizer`), the local HTTP/SSE daemon (`humanizer serve`), the CLI (`humanizer run`), and the underlying Gemini engine.
3. **Frictionless Distribution:** A standalone Windows single-file executable (`humanizer.exe`) built via PyInstaller that runs out-of-the-box on systems without Python installed, defaulting to launching the REST server when clicked.

---

## 2. Markdown & Structural Chunking Architecture (Requirement R3)

### 2.1 The Structural Preservation Challenge
When LLMs rewrite technical or structured prose, common failure modes include:
- Modifying variable names, code logic, or syntax inside fenced code blocks.
- Hallucinating or paraphrasing inline code keywords (e.g., changing `` `process_order()` `` to `` `handle_order()` ``).
- Flattening or mangling bullet list indentation, numbered lists, or blockquotes.
- Breaking Markdown table pipes (`|`), header delimiters (`|---|`), and cell alignments.
- Dropping paragraphs or summarizing text when fed oversized blocks.

To eliminate these failure modes, we design a **Two-Tier Parser: Block State Machine + Safe Inline Token Masking**.

```
Source Document (Markdown)
          │
          ▼
┌───────────────────────────────────────┐
│       Block Parser State Machine      │
└───────────────────────────────────────┘
          │
          ├── Code Blocks (```) ───────► Marked as IMMUTABLE (Bypass LLM)
          ├── Tables (|...|) ──────────► Marked as IMMUTABLE (Bypass LLM)
          ├── Blank Lines / Rules ────► Marked as IMMUTABLE (Bypass LLM)
          │
          └── Humanizable Blocks ──────► Headers, Paragraphs, List Items
                         │
                         ▼
          ┌─────────────────────────────┐
          │   Inline Masking Engine     │
          │  (`code` -> ⟦CODE_0⟧)       │
          │  ([link](url) -> ⟦URL_0⟧)   │
          └─────────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │   Semantic Chunk Grouper    │
          │   (Target: 1000-2000 chars, │
          │    Respects Headers/Blank)  │
          └─────────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │   Gemini Humanizer Engine   │
          └─────────────────────────────┘
                         │
                         ▼
          ┌─────────────────────────────┐
          │   Inline Unmasking Engine   │
          │  (⟦CODE_0⟧ -> `code`)       │
          └─────────────────────────────┘
                         │
                         ▼
┌───────────────────────────────────────┐
│         Reassembly Pipeline           │
│  (Restores exact newlines & spacing)  │
└───────────────────────────────────────┘
          │
          ▼
  Faithful Humanized Output Document
```

---

### 2.2 Markdown Element Identification Specifications

#### A. Fenced Code Blocks
- **Opening Fence Regex:** `^([ ]{0,3})(`{3,}|~{3,})([^\n`]*)$`
  - Captures leading indentation (up to 3 spaces), fence character (`` ` `` or `~`), fence length (≥ 3), and optional language tag (e.g., `python`, `json`, `bash`).
- **Closing Fence Regex:** Matches the same fence character with a length greater than or equal to the opening fence, with no trailing content other than optional whitespace: `^([ ]{0,3})(`{3,}|~{3,})\s*$`
- **Behavior:** All lines between opening and closing fences are treated as an atomic `CodeBlock`.
  - `is_humanizable = False`
  - Completely bypassed from the LLM prompt. Preserved bit-for-bit, byte-for-byte.

#### B. Tables (GFM Syntax)
- **Header Line:** `^\s*\|(.+)\|\s*$`
- **Delimiter Line:** `^\s*\|(\s*:?-+:?\s*\|)+\s*$`
- **Data Lines:** `^\s*\|(.+)\|\s*$`
- **Behavior:** Tables are grouped as `TableBlock`.
  - `is_humanizable = False` (or cell-content humanization mode if explicitly requested).
  - Preserves pipe delimiters, dashes, and column spacing intact.

#### C. ATX Headings
- **Regex:** `^(#{1,6})\s+(.+?)(?:\s+#+)?$`
- **Behavior:** Extracted as `HeaderBlock`.
  - Prefix: `#{1,6} ` (preserved).
  - Content: Header title text.
  - Serves as a hard semantic chunk boundary so sections are never lumped awkwardly together.

#### D. List Items
- **Unordered Item Regex:** `^([ ]*)([-*+])\s+(.+)$`
- **Ordered Item Regex:** `^([ ]*)(\d+[.)])\s+(.+)$`
- **Behavior:** Extracted as `ListItemBlock`.
  - Preserves exact indentation (`m.group(1)`), marker (`m.group(2)`), and space.
  - Content is passed through humanization with inline masking applied.

#### E. Blockquotes
- **Regex:** `^([ ]*>+\s?)(.*)$`
- **Behavior:** Preserves quote prefix `> `, humanizes the quoted message.

#### F. Thematic Breaks / Horizontal Rules
- **Regex:** `^([ ]{0,3})([-*_][ ]*){3,}\s*$`
- **Behavior:** Immutable `SeparatorBlock`.

---

### 2.3 Safe Inline Token Masking

Within any humanizable text (paragraphs, list item bodies, blockquotes), inline code and URLs must not be altered by the LLM:

1. **Inline Code:** Matches `` `([^`\n]+)` `` or ```` ``([^`\n]+)`` ````.
   - Replaced with: `⟦CODE_0⟧`, `⟦CODE_1⟧`, etc.
   - Sentinel characters `⟦` and `⟧` (Unicode `U+27E6` and `U+27E7`) are distinct, never confused with markdown syntax, and rarely generated by LLMs spontaneously.
2. **Markdown Links:** Matches `\[([^\]]+)\]\(([^)\s]+)\)`.
   - The anchor text can be rewritten naturally for tone, but the target URL is masked: `[anchor](⟦URL_0⟧)`.
3. **Inline Math:** Matches `\$([^$\n]+)\$`.
   - Replaced with: `⟦MATH_0⟧`.
4. **LLM System Directive:**
   The prompt explicitly contains:
   `"CRITICAL: Retain all placeholder tokens like ⟦CODE_0⟧, ⟦URL_0⟧, and ⟦MATH_0⟧ exactly as written without altering or translating them."`
5. **Post-Processing Unmask:**
   A regex substitution `re.sub(r'⟦CODE_(\d+)⟧', ...)` injects the original preserved strings back into the humanized text. If the LLM dropped a placeholder, a fallback recovery heuristic restores it based on proximity.

---

### 2.4 Semantic Paragraph Grouping & Chunking

For long documents (multi-page papers, essays, long technical blogs):
- **Chunk Target Size:** Configurable `max_chunk_chars` (default: 1,500 characters, ~250–350 words).
- **Hard Boundaries:**
  - Header encounters (`#`, `##`, `###`) immediately flush the current chunk to maintain section coherence.
  - Fenced code blocks and tables are never merged with prose; they are emitted as atomic non-LLM chunks.
- **Soft Boundaries:**
  - Paragraph separations (two or more newlines `\n\n+`).
- **Oversized Paragraph Handling:**
  - If a single paragraph exceeds `max_chunk_chars`, it is split along sentence boundaries using a regex lookbehind:
    `(?<=[.!?])\s+(?=[A-Z0-9"\'])`
  - Sentences are recombined up to `max_chunk_chars`, ensuring no sentence is cut mid-phrase.

---

### 2.5 Document Reassembly

The parser produces a sequence of blocks with metadata:
```python
class BlockType(str, Enum):
  CODE = "code"
  TABLE = "table"
  HEADER = "header"
  LIST_ITEM = "list_item"
  PARAGRAPH = "paragraph"
  QUOTE = "quote"
  BLANK = "blank"
  SEPARATOR = "separator"


@dataclass
class DocumentBlock:
  block_type: BlockType
  raw_text: str
  is_humanizable: bool
  prefix: str = ""
  content: str = ""
  suffix: str = ""
  indent: str = ""
```
Reassembly iterates through the sequence:
- For immutable blocks (`CODE`, `TABLE`, `BLANK`, `SEPARATOR`), the `raw_text` is appended verbatim.
- For humanized blocks, `f"{block.indent}{block.prefix}{humanized_content}{block.suffix}"` is appended.
- Original spacing between blocks is retained, achieving 100% layout fidelity.

---

## 3. FastAPI / Uvicorn Local Daemon & SSE Architecture (Requirement R1)

### 3.1 Overview
The daemon provides a local, zero-configuration microservice that exposes standard REST and real-time streaming endpoints. It acts as the local bridge for:
- Desktop GUIs or web frontends.
- Browser extensions.
- Shell scripts or external editor plugins (VS Code, Obsidian).

```
                      ┌─────────────────────────────────┐
                      │    FastAPI Application (/docs)   │
                      └────────────────┬────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────┐                             ┌───────────────────────┐
│   POST /v1/humanize   │                             │ POST /v1/humanize/    │
│  (Synchronous JSON)   │                             │ stream (SSE Stream)   │
└───────────┬───────────┘                             └───────────┬───────────┘
            │                                                     │
            │   ┌─────────────────────────────────────────────┐   │
            └──►│          Humanizer Engine Instance          │◄──┘
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────┐
                        │   Google GenAI Flash Lite   │
                        └─────────────────────────────┘
```

---

### 3.2 CLI Entry Point: `humanizer serve`

The CLI is built using Python's standard `argparse` to minimize external dependencies and avoid PyInstaller dynamic import issues.

```bash
# Start daemon with defaults (127.0.0.1:8000)
humanizer serve

# Start on custom port and host
humanizer serve --host 0.0.0.0 --port 8080

# Run in development reload mode
humanizer serve --reload
```

CLI argument parser implementation:
```python
import argparse
import sys
import uvicorn


def main():
  parser = argparse.ArgumentParser(
      prog="humanizer",
      description="Jade's AI Humanizer - Local Library, CLI, and Daemon",
  )
  subparsers = parser.add_subparsers(dest="command", help="Available commands")

  # 'serve' subcommand
  serve_parser = subparsers.add_parser("serve", help="Start local REST daemon")
  serve_parser.add_argument(
      "--host",
      default="127.0.0.1",
      help="Bind host interface (default: 127.0.0.1)",
  )
  serve_parser.add_argument(
      "--port",
      type=int,
      default=8000,
      help="Bind port number (default: 8000)",
  )
  serve_parser.add_argument(
      "--reload", action="store_true", help="Enable live auto-reload for dev"
  )

  # 'run' subcommand
  run_parser = subparsers.add_parser(
      "run", help="Humanize a file or piped text directly"
  )
  run_parser.add_argument(
      "input_file",
      nargs="?",
      default="-",
      help="Path to input text file or '-' for stdin",
  )
  run_parser.add_argument(
      "-o", "--output", help="Path to output file (default: stdout)"
  )
  run_parser.add_argument(
      "--mode",
      choices=["budget", "deep"],
      default="budget",
      help="Humanization mode",
  )
  run_parser.add_argument(
      "--tone",
      choices=["neutral", "casual", "academic", "professional"],
      default="neutral",
  )

  args = parser.parse_args()

  if args.command == "serve":
    from humanizer.daemon.app import create_app

    app = create_app()
    print(f"[*] Starting Humanizer Daemon on http://{args.host}:{args.port}")
    print(f"[*] Interactive Swagger Docs: http://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
  elif args.command == "run":
    # CLI execution
    pass
  else:
    parser.print_help()
    sys.exit(1)
```

---

### 3.3 Endpoints Specification

#### 1. Health Check: `GET /health`
- **Purpose:** Liveness probe and configuration status.
- **Status Code:** 200 OK
- **Response Schema:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "engine": "gemini-2.5-flash-lite",
  "api_key_configured": true,
  "default_mode": "budget"
}
```

#### 2. Synchronous Humanization: `POST /v1/humanize`
- **Request Body:**
```json
{
  "text": "The aforementioned methodology utilizes a plethora of intricate algorithms...",
  "mode": "budget",
  "tone": "neutral",
  "reading_level": "intermediate",
  "preserve_markdown": true,
  "api_key": null
}
```
- **Response Schema:**
```json
{
  "humanized_text": "Our approach uses several straightforward algorithms...",
  "mode": "budget",
  "tone": "neutral",
  "stats": {
    "original_chars": 76,
    "humanized_chars": 54,
    "prompt_tokens_overhead": 82,
    "latency_ms": 215
  }
}
```

#### 3. Server-Sent Events (SSE) Streaming: `POST /v1/humanize/stream`
- **Content-Type:** `text/event-stream`
- **Header Requirements:** `Cache-Control: no-cache`, `Connection: keep-alive`
- **Streaming Implementation (Native FastAPI StreamingResponse):**
  Does NOT require extra external dependencies like `sse-starlette`; uses Starlette's built-in `StreamingResponse`:
```python
from fastapi.responses import StreamingResponse


@router.post("/v1/humanize/stream")
async def humanize_stream(request: HumanizeRequest):
  async def event_publisher():
    async for chunk_event in humanizer.humanize_stream_async(
        text=request.text,
        mode=request.mode,
        tone=request.tone,
        preserve_markdown=request.preserve_markdown,
    ):
      data = json.dumps(chunk_event)
      yield f"data: {data}\n\n"
    yield "data: [DONE]\n\n"

  return StreamingResponse(event_publisher(), media_type="text/event-stream")
```
- **Event Wire Format:**
```
data: {"event": "start", "total_chunks": 3}

data: {"event": "chunk", "index": 0, "text": "Our approach uses "}

data: {"event": "chunk", "index": 1, "text": "several straightforward algorithms..."}

data: {"event": "stats", "latency_ms": 198, "overhead_tokens": 82}

data: [DONE]
```

#### 4. OpenAPI / Swagger Documentation: `/docs`
- Automatic interactive testing console generated by FastAPI at `http://127.0.0.1:8000/docs`.
- Schema models defined with Pydantic v2 with field descriptions, validation ranges, and examples.
- CORS enabled globally via `CORSMiddleware` with `allow_origins=["*"]` to allow local browser extensions and web tools to query without CORS blocks.

---

### 3.4 In-Process Python SDK (`from humanizer import Humanizer`)

The library is designed for direct embedding into any Python project:
```python
from humanizer import Humanizer

# Automatically reads GEMINI_API_KEY from environment, or takes explicit parameter
client = Humanizer(api_key="...", mode="budget", tone="neutral")

# 1. Synchronous execution
clean_text = client.humanize("AI-generated text goes here...")

# 2. Asynchronous execution
clean_text = await client.humanize_async("AI-generated text goes here...")

# 3. Synchronous streaming generator
for chunk in client.humanize_stream("Long markdown document..."):
  print(chunk, end="", flush=True)

# 4. Asynchronous streaming generator
async for chunk in client.humanize_stream_async("Long markdown document..."):
  print(chunk, end="", flush=True)
```

---

## 4. Standalone Windows Executable (`humanizer.exe`) Packaging Architecture

### 4.1 Packaging Goals & Constraints
- **Zero Python Pre-requisite:** Users can download a single binary `humanizer.exe` and run the daemon without having Python, pip, or virtual environments installed.
- **Single-File Artifact (`--onefile`):** Produces a single `.exe` file that unbundles into a temporary execution folder (`sys._MEIPASS`) and executes cleanly.
- **Zero-Friction Launch UX:** Double-clicking `humanizer.exe` in Windows Explorer automatically launches the server on `http://127.0.0.1:8000` with an active console banner showing instructions and the Swagger URL.

---

### 4.2 PyInstaller Technical Traps & Solutions

#### Trap 1: `uvicorn.run("module:app")` Reflection Failure
In frozen PyInstaller bundles, Uvicorn's default dynamic string import (`"humanizer.daemon.app:app"`) fails with `ModuleNotFoundError` because the frozen importer cannot resolve standard filesystem module paths.
- **Solution:** Always pass the initialized FastAPI app object directly:
  `uvicorn.run(app, host=host, port=port)`
  Passing the instance completely bypasses Uvicorn's reflection mechanism.

#### Trap 2: Multiprocessing Fork Bomb on Windows
When PyInstaller spawns subprocesses on Windows without `multiprocessing.freeze_support()`, the executable reinvokes itself in an infinite loop.
- **Solution:** Call `multiprocessing.freeze_support()` as the very first line of the executable launcher before any application imports.

#### Trap 3: Missing Hidden Imports for Uvicorn & FastAPI
Uvicorn lazily imports protocol handlers, event loops, and lifespan managers that PyInstaller's static AST analysis cannot detect.
- **Solution:** Explicitly list hidden imports in the build spec:
  - `uvicorn.logging`
  - `uvicorn.loops.auto`
  - `uvicorn.loops.asyncio`
  - `uvicorn.protocols.http.auto`
  - `uvicorn.protocols.http.h11_impl`
  - `uvicorn.lifespan.on`
  - `starlette.routing`
  - `pydantic_core`
  - `google.genai`

---

### 4.3 Dedicated Frozen Launcher: `packaging/entrypoint.py`

```python
"""Standalone Windows entrypoint for PyInstaller packaging.

Handles multiprocessing freeze support and provides smart dual-mode behavior:
1. Double-click in Windows Explorer (no args) -> starts 'serve' daemon.
2. CLI execution (with args) -> executes standard CLI commands.
"""

import multiprocessing
import os
import sys

if __name__ == "__main__":
  # Crucial for Windows PyInstaller binaries
  multiprocessing.freeze_support()

  # Ensure UTF-8 output on Windows console
  if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

  from humanizer.cli import main

  # If invoked with no arguments (e.g. user double-clicked the exe in Explorer),
  # default to launching the daemon server
  if len(sys.argv) == 1:
    print("=" * 60)
    print("       Jade's AI Humanizer - Local REST API Daemon")
    print("=" * 60)
    print("No CLI arguments detected. Starting local daemon automatically...")
    sys.argv.append("serve")

  sys.exit(main())
```

---

### 4.4 PyInstaller Spec Specification: `packaging/humanizer.spec`

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = []
binaries = []
hiddenimports = [
    "uvicorn",
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "starlette",
    "pydantic",
    "pydantic_core",
    "google.genai",
]

# Collect all dynamic assets, schemas, and binaries
for pkg in ["fastapi", "uvicorn", "pydantic", "pydantic_core", "google.genai"]:
  pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
  datas += pkg_datas
  binaries += pkg_binaries
  hiddenimports += pkg_hidden

a = Analysis(
    ["entrypoint.py"],
    pathex=["../src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "scipy", "notebook"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="humanizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
```

---

### 4.5 Automated Build Script: `packaging/build_exe.py`

A script that checks prerequisites, invokes PyInstaller, verifies the generated binary, and outputs the final artifact into `dist/humanizer.exe`:

```python
"""Automated build and packaging script for Windows standalone executable."""

import os
from pathlib import Path
import subprocess
import sys


def build_executable():
  project_root = Path(__file__).resolve().parent.parent
  spec_path = project_root / "packaging" / "humanizer.spec"
  dist_path = project_root / "dist"

  print(f"[*] Building humanizer.exe using spec: {spec_path}")
  cmd = [
      sys.executable,
      "-m",
      "PyInstaller",
      "--clean",
      "--noconfirm",
      "--distpath",
      str(dist_path),
      str(spec_path),
  ]

  result = subprocess.run(cmd, cwd=project_root / "packaging")
  if result.returncode != 0:
    print("[!] PyInstaller build failed!")
    sys.exit(result.returncode)

  exe_path = dist_path / "humanizer.exe"
  if exe_path.exists():
    size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"[+] Build successful! Output: {exe_path} ({size_mb:.2f} MB)")
  else:
    print("[!] Error: humanizer.exe was not found in dist/")
    sys.exit(1)


if __name__ == "__main__":
  build_executable()
```

---

## 5. Documentation Requirements Blueprint (Requirement R4 & Global Rules)

The repository root must maintain three documents adhering to professional open-source standards:

### 5.1 `README.md` Specifications
Must be structured with clear copy-paste examples:
1. **Title & Badges:** "Jade's AI Humanizer - Zero-Backend Client-Side Text Humanizer & REST Daemon".
2. **Key Capabilities:**
   - Single-pass `budget` mode (<100 prompt token overhead).
   - Multi-layered `deep` mode.
   - Markdown & code block structural invariance.
   - Zero telemetry, local-first execution.
3. **Installation:**
   - Via pip / source install.
   - Standalone Windows `.exe` download instructions.
4. **Environment Configuration:**
   - Setting `GEMINI_API_KEY` in environment.
5. **Python Library Quickstart:**
   - Code snippets for `Humanizer.humanize()`, `Humanizer.humanize_async()`, and `Humanizer.humanize_stream()`.
6. **Local REST API Daemon Quickstart:**
   - Command `humanizer serve --port 8000`.
   - cURL example for `POST /v1/humanize`.
   - cURL example for SSE streaming `POST /v1/humanize/stream`.
   - Link to interactive Swagger `/docs`.
7. **CLI Usage:**
   - `humanizer run input.md -o output.md --mode budget --tone casual`.
8. **Configuration Reference:**
   - Table of modes (`budget`, `deep`), tones (`neutral`, `casual`, `academic`, `professional`), and reading levels.
9. **Building Standalone EXE:**
   - Steps to execute `python packaging/build_exe.py`.

### 5.2 `CHANGELOG.md` Specifications
Adheres to [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and Semantic Versioning (`1.0.0`):
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-10

### Added
- Core `Humanizer` Python library with synchronous and asynchronous methods.
- Single-pass `budget` mode with strict token overhead minimization (<100 prompt tokens).
- Multi-layered `deep` paraphrasing mode.
- Markdown and structural chunking parser preserving code blocks, headers, lists, and tables.
- Inline code and link masking engine ensuring technical keywords remain unmodified.
- FastAPI/Uvicorn local daemon (`humanizer serve`) exposing `/health`, `/v1/humanize`, and `/docs`.
- Real-time Server-Sent Events (SSE) streaming endpoint (`/v1/humanize/stream`).
- Standalone Windows executable `humanizer.exe` bundling via PyInstaller with click-to-run auto-serve.
- Automated grammar verification and AI cliché vocabulary audit guardrails.
```

### 5.3 `TODO.md` Specifications
Structured for transparent roadmap tracking:
```markdown
# Project Roadmap & TODO

## Phase 1: Core Release (Current)
- [x] Initial architecture specification and packaging blueprint.
- [ ] Implement Markdown structural block parser and inline masking.
- [ ] Implement Token-minimized Gemini Flash Lite engine (Budget & Deep).
- [ ] Implement FastAPI daemon and SSE streaming endpoint.
- [ ] Implement CLI entry points (`humanizer serve`, `humanizer run`).
- [ ] Build and verify standalone Windows `humanizer.exe`.
- [ ] Maintain comprehensive README.md, CHANGELOG.md, and TODO.md in repo root.

## Phase 2: Enhanced Formats & Extensions (Future)
- [ ] Direct DOCX and PDF document humanization with formatting preservation.
- [ ] Browser extension bridge (Chrome/Firefox extension connecting to localhost:8000).
- [ ] Desktop GUI wrapper (Tkinter / CustomTkinter frontend bundled in the exe).
- [ ] Multi-lingual humanization presets (Spanish, French, German, Japanese).
```

---

## 6. Recommended Repository Code Layout

To adhere to Python Packaging Authority (PyPA) best practices and avoid import confusion, the project must utilize the standard `src`-layout:

```
Jade's AI Humanizer/
├── .agents/                      # Teamwork agent metadata & reports
├── src/
│   └── humanizer/
│       ├── __init__.py           # Exports: Humanizer, __version__
│       ├── __main__.py           # Allows: python -m humanizer
│       ├── cli.py                # CLI parser (serve, run, version)
│       ├── client.py             # Humanizer high-level interface (sync/async/stream)
│       ├── config.py             # Presets, Tone, Mode, constants
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── gemini.py         # Google GenAI Flash Lite SDK client wrapper
│       │   ├── prompts.py        # Budget (<100 tokens) & Deep system instructions
│       │   ├── guardrails.py     # AI buzzword ban audit & syntax verification
│       │   └── token_counter.py  # Token counting & overhead verification
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── chunker.py        # Semantic document chunker along paragraph boundaries
│       │   ├── markdown.py       # Markdown state-machine block parser
│       │   └── mask.py           # Inline code and URL masking/unmasking engine
│       └── daemon/
│           ├── __init__.py
│           ├── app.py            # FastAPI app initialization, CORS, and lifespan
│           ├── routes.py         # Endpoints: /health, /v1/humanize, /v1/humanize/stream
│           └── schemas.py        # Pydantic v2 request & response schemas
├── packaging/
│   ├── build_exe.py              # Automated PyInstaller build script
│   ├── entrypoint.py             # Frozen launcher with freeze_support() & auto-serve
│   └── humanizer.spec            # PyInstaller spec with hidden imports & data hooks
├── tests/
│   ├── __init__.py
│   ├── test_client.py            # Unit tests for Humanizer sync & async API
│   ├── test_markdown_chunker.py  # Markdown parsing, code block, and list tests
│   ├── test_mask.py              # Inline code and URL placeholder tests
│   ├── test_guardrails.py        # Buzzword audit and grammar syntax tests
│   ├── test_budget_tokens.py     # Prompt token overhead verification (<100 tokens)
│   └── test_daemon.py            # FastAPI endpoints, Swagger docs, and SSE stream tests
├── pyproject.toml                # Modern PEP 621 / Hatchling project configuration
├── requirements.txt              # Runtime dependencies (google-genai, fastapi, uvicorn, pydantic)
├── requirements-dev.txt          # Development dependencies (pytest, pytest-asyncio, httpx, pyinstaller)
├── README.md                     # Root documentation
├── CHANGELOG.md                  # Release log
└── TODO.md                       # Active roadmap
```

---

## 7. Verification & Testing Matrix

| Requirement | Acceptance Criterion | Verification Method |
|---|---|---|
| **R1 (Library Sync/Async)** | `from humanizer import Humanizer` executes sync & async calls cleanly | `pytest tests/test_client.py` |
| **R1 (Daemon)** | `humanizer serve` starts daemon, returns 200 on `/health` and valid JSON on `/v1/humanize` | `pytest tests/test_daemon.py -k test_health_and_humanize` |
| **R1 (SSE)** | `/v1/humanize/stream` delivers chunked text stream without drops | `pytest tests/test_daemon.py -k test_sse_streaming` using `httpx.AsyncClient` |
| **R1 (Packaging)** | Standalone `humanizer.exe` builds and responds to local HTTP requests | `python packaging/build_exe.py` followed by executing `dist/humanizer.exe serve --port 8999` and hitting `http://127.0.0.1:8999/health` |
| **R3 (Markdown Code Preservation)** | Fenced code blocks (` ``` `) and inline code (`` ` ``) remain 100% bit-for-bit identical | `pytest tests/test_markdown_chunker.py -k test_code_block_preservation` |
| **R3 (Markdown Structure)** | Headers (`#`), lists (`-`, `1.`), and tables (`|`) retain exact formatting | `pytest tests/test_markdown_chunker.py -k test_structure_preservation` |
| **R4 (Documentation)** | `README.md`, `CHANGELOG.md`, `TODO.md` exist and contain required sections | Automated file existence and header inspection |
