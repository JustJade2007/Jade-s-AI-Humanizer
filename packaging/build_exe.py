"""PyInstaller build script for Jade's AI Humanizer executable."""

import os
import subprocess
import sys
from pathlib import Path


def build():
    workspace = Path(__file__).resolve().parent.parent
    src_dir = workspace / "src"
    entrypoint = src_dir / "humanizer" / "cli.py"
    dist_dir = workspace / "dist"

    print(f"Building standalone Windows executable from {entrypoint}...")
    print(f"Workspace: {workspace}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "humanizer",
        "--paths",
        str(src_dir),
        "--collect-all",
        "humanizer",
        "--collect-all",
        "uvicorn",
        "--collect-all",
        "starlette",
        "--collect-all",
        "fastapi",
        "--collect-all",
        "sse_starlette",
        "--copy-metadata",
        "google-genai",
        "--copy-metadata",
        "fastapi",
        "--copy-metadata",
        "uvicorn",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols",
        "--hidden-import",
        "uvicorn.protocols.http",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan",
        "--hidden-import",
        "uvicorn.lifespan.on",
        str(entrypoint),
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(workspace))
    if result.returncode != 0:
        print(f"PyInstaller build failed with exit code {result.returncode}", file=sys.stderr)
        sys.exit(result.returncode)

    exe_path = dist_dir / "humanizer.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\nSUCCESS: Built standalone executable at {exe_path} ({size_mb:.2f} MB)")
    else:
        print(f"\nERROR: Executable not found at {exe_path}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    build()
