"""Jade's AI Humanizer - Zero-Backend Client-Side Text Humanizer & REST Daemon."""

from humanizer.client import Humanizer
from humanizer.models import (
    HumanizeResult,
    ModePreset,
    ReadingLevelPreset,
    TonePreset,
    UsageMetadata,
)
from humanizer.parser import DocumentChunk, InlineMasker, MarkdownDocument

__version__ = "1.2.2"

__all__ = [
    "Humanizer",
    "HumanizeResult",
    "UsageMetadata",
    "TonePreset",
    "ReadingLevelPreset",
    "ModePreset",
    "MarkdownDocument",
    "DocumentChunk",
    "InlineMasker",
    "__version__",
]
