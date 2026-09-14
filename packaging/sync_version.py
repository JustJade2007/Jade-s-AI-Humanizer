"""Synchronize version numbers across pyproject.toml and src/humanizer/__init__.py."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def sync_version(version: str | None = None) -> str:
    """Synchronize project version from input, environment, or Git tag."""
    if not version:
        version = os.environ.get("PACKAGE_VERSION", "").strip()
    if not version:
        ref = os.environ.get("GITHUB_REF", "")
        if ref.startswith("refs/tags/"):
            version = os.environ.get("GITHUB_REF_NAME", "").strip()
    if not version:
        print("No target version override specified; maintaining existing version.")
        return ""

    version = version.lstrip("v").strip()
    if not version:
        return ""

    print(f"Synchronizing package version to: {version}")

    # 1. pyproject.toml
    pyproject_file = ROOT_DIR / "pyproject.toml"
    if pyproject_file.exists():
        content = pyproject_file.read_text(encoding="utf-8")
        new_content = re.sub(
            r'version\s*=\s*"[^"]+"',
            f'version = "{version}"',
            content,
        )
        pyproject_file.write_text(new_content, encoding="utf-8")
        print(f"Updated {pyproject_file}")

    # 2. src/humanizer/__init__.py
    init_file = ROOT_DIR / "src" / "humanizer" / "__init__.py"
    if init_file.exists():
        content = init_file.read_text(encoding="utf-8")
        new_content = re.sub(
            r'__version__\s*=\s*"[^"]+"',
            f'__version__ = "{version}"',
            content,
        )
        init_file.write_text(new_content, encoding="utf-8")
        print(f"Updated {init_file}")

    return version


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    sync_version(target)
