"""Engine package containing generator, prompts, guardrails, readability, and deep paraphraser."""

from humanizer.engine.deep import DeepParaphraser
from humanizer.engine.generator import GeminiGenerator
from humanizer.engine.guardrails import (
    audit_vocabulary,
    replace_banned_buzzwords,
    sanitize_and_verify_grammar,
)
from humanizer.engine.prompt import (
    estimate_prompt_tokens,
    get_budget_prompt,
    get_deep_prompt,
)
from humanizer.engine.readability import (
    calculate_flesch_kincaid_grade,
    calculate_flesch_reading_ease,
    calculate_readability,
    count_syllables,
)

from humanizer.engine.thesaurus import deflate_descriptors

__all__ = [
    "GeminiGenerator",
    "DeepParaphraser",
    "get_budget_prompt",
    "get_deep_prompt",
    "estimate_prompt_tokens",
    "calculate_readability",
    "calculate_flesch_reading_ease",
    "calculate_flesch_kincaid_grade",
    "count_syllables",
    "audit_vocabulary",
    "replace_banned_buzzwords",
    "sanitize_and_verify_grammar",
    "deflate_descriptors",
]
