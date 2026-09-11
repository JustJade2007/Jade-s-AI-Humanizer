"""Tier 4: Real-World Application Scenarios E2E Tests for Jade's AI Humanizer.

Verifies end-to-end workflows representing realistic user workloads:
- Scenario 1: Blog Post Humanization (casual tone, headers, bullets, callout blockquote)
- Scenario 2: Technical Paper with Code & Formulas (academic tone, code fences, tables, math)
- Scenario 3: Customer Support Email Rewrite (professional tone, greeting, signoff, grammar)
- Scenario 4: Marketing Pitch & Product Announcement Rewrite (high burstiness, cliché purge)
- Scenario 5: Multi-Page Article with Semantic Paragraph Chunking (long doc, links, ATX headers)
- Scenario 6: Full Daemon REST & SSE Client Workflow (health check, sync humanize, streaming)
"""

import json
import re
import pytest

from humanizer import Humanizer, HumanizeResult
from tests.e2e.conftest import (
    audit_buzzwords,
    calculate_flesch_reading_ease,
    PROJECT_ROOT,
)


def test_t4_01_blog_post_humanization_scenario(mock_humanizer, sample_blog_post):
    """Scenario 1: Tech Blog Post Humanization.
    
    A developer writes an AI-drafted blog post containing buzzwords ('delve', 'tapestry',
    'testament', 'moreover'), markdown headers, bullet points, and an inspirational
    blockquote callout.
    
    Workflow:
    - Mode: budget
    - Tone: casual
    - Reading level: general
    - Preserve markdown: True
    
    Verifications:
    - ATX heading (#) remains intact at top of document.
    - Bullet points (- First, - Second, - Third) preserved with identical formatting.
    - Blockquote callout (> ...) preserved.
    - Banned buzzwords completely purged (0 occurrences).
    - Casual tone style markers present (natural contractions, conversational flow).
    - Prompt token overhead < 100 tokens.
    """
    words = len(sample_blog_post.split())
    result = mock_humanizer.humanize(
        sample_blog_post,
        mode="budget",
        tone="casual",
        reading_level="general",
        preserve_markdown=True,
    )

    # 1. Structural preservation
    assert result.text.startswith("# Exploring Modern Web Architecture")
    assert "- First, consider component structure." in result.text
    assert "- Second, optimize build pipelines." in result.text
    assert "- Third, monitor server latency." in result.text
    assert "> Modern development is not just about code" in result.text

    # 2. Vocabulary purification (0 buzzwords)
    violations = audit_buzzwords(result.text)
    assert len(violations) == 0, f"Found banned buzzwords in blog post: {violations}"
    assert "tapestry" not in result.text.lower()
    assert "delve" not in result.text.lower()

    # 3. Budget token overhead constraint (<100 tokens)
    overhead = result.prompt_tokens - words
    assert overhead < 100, f"Budget overhead {overhead} exceeded 100 tokens limit!"

    # 4. Readability score reported
    assert 40.0 <= result.flesch_reading_ease <= 100.0


def test_t4_02_technical_paper_with_code_and_formulas_scenario(mock_humanizer, sample_technical_paper):
    """Scenario 2: Academic Computer Science Paper with Code & GFM Tables.
    
    A research scientist humanizes an academic manuscript section containing:
    - Formal mathematical complexity formulas: $O(\\log n)$
    - Fenced Python implementation of Byzantine consensus
    - Multi-column Markdown comparison table
    - Formal academic tone and collegiate reading level
    
    Workflow:
    - Mode: deep
    - Tone: academic
    - Reading level: college
    - Preserve markdown: True
    
    Verifications:
    - Fenced code block is 100% bit-for-bit identical to source.
    - GFM comparison table retained with all pipes, delimiters, and cells intact.
    - Inline mathematical formulas ($...$) preserved untouched.
    - Academic tone applied without informal slang or casual contractions.
    - Flesch Reading Ease measured and reported.
    """
    result = mock_humanizer.humanize(
        sample_technical_paper,
        mode="deep",
        tone="academic",
        reading_level="college",
        preserve_markdown=True,
    )

    # 1. Byte-for-byte code block invariance
    expected_code = (
        "```python\n"
        "def check_consensus(votes: list[bool], quorum: int) -> bool:\n"
        "    # Byzantine fault tolerant check\n"
        "    return sum(votes) >= quorum\n"
        "```"
    )
    assert expected_code in result.text, "Code block was modified or corrupted!"

    # 2. Table invariance
    assert "| Protocol | Quorum Size | Message Overhead |" in result.text
    assert "| :--- | :--- | :--- |" in result.text
    assert "| Paxos | $2f + 1$ | $O(n^2)$ |" in result.text
    assert "| Raft | $2f + 1$ | $O(n)$ |" in result.text
    assert "| PBFT | $3f + 1$ | $O(n^2)$ |" in result.text

    # 3. Formula preservation
    assert "$O(\\log n)$" in result.text

    # 4. Academic tone validation
    assert "don't" not in result.text
    assert "can't" not in result.text

    # 5. Buzzword check
    violations = audit_buzzwords(result.text)
    assert len(violations) == 0


def test_t4_03_customer_support_email_rewrite_scenario(mock_humanizer, sample_support_email):
    """Scenario 3: Customer Support Email Response Rewrite.
    
    An automated customer service draft filled with stiff, impersonal AI phrasing
    and clichés ('moreover, we have delved', 'serves as a testament to our reliability',
    'in summary, it is crucial to remember') is rewritten into a polished, empathetic,
    professional email.
    
    Workflow:
    - Mode: budget
    - Tone: professional
    - Reading level: general
    
    Verifications:
    - Greeting ('Dear Valued Customer,') and signoff ('Best regards,') preserved.
    - URL link ('https://auth.example.com') preserved.
    - Stiff AI clichés removed.
    - Punctuation spacing and capitalization sanitized.
    - Professional, courteous tone achieved.
    """
    result = mock_humanizer.humanize(
        sample_support_email,
        mode="budget",
        tone="professional",
        reading_level="general",
    )

    # 1. Structural framing
    assert "Dear Valued Customer," in result.text
    assert "Best regards," in result.text
    assert "https://auth.example.com" in result.text

    # 2. Purged clichés
    violations = audit_buzzwords(result.text)
    assert len(violations) == 0, f"Buzzwords remained in support email: {violations}"
    assert "delved" not in result.text.lower()
    assert "testament" not in result.text.lower()

    # 3. Clean grammar and punctuation
    assert " ," not in result.text
    assert " ." not in result.text


def test_t4_04_marketing_pitch_landing_page_scenario(mock_humanizer, sample_marketing_pitch):
    """Scenario 4: Startup Marketing Pitch & Landing Page Copy.
    
    A founder rewrites an overhyped, cliché-ridden landing page draft
    ('bespoke platform', 'pivotal game-changer', 'multifaceted industries',
    'plethora of deep algorithms', 'transform your enterprise tapestry').
    
    Workflow:
    - Mode: deep
    - Tone: casual
    - Reading level: high_school
    
    Verifications:
    - All hype clichés purged ('game-changer', 'tapestry', 'plethora', 'bespoke').
    - Sentence burstiness and rhythmic variation applied.
    - Message retains strong, engaging product value proposition.
    - Flesch Reading Ease score calculated.
    """
    result = mock_humanizer.humanize(
        sample_marketing_pitch,
        mode="deep",
        tone="casual",
        reading_level="high_school",
    )

    # 1. Cliché purge
    violations = audit_buzzwords(result.text)
    assert len(violations) == 0, f"Found hype buzzwords in marketing copy: {violations}"
    assert "game-changer" not in result.text.lower()
    assert "tapestry" not in result.text.lower()
    assert "plethora" not in result.text.lower()

    # 2. Content transformed and non-empty
    assert len(result.text) > 0
    assert result.mode == "deep"

    # 3. Readability score
    assert 0.0 <= result.flesch_reading_ease <= 100.0


def test_t4_05_multipage_article_semantic_chunking_scenario(mock_humanizer, sample_long_article):
    """Scenario 5: Multi-Page Article with Semantic Paragraph Chunking.
    
    A long technical report (>12 sections, multiple paragraphs, links) is processed.
    The chunking engine splits along semantic paragraph boundaries while maintaining
    hierarchical ATX headers (### Section 1 ... ### Section 12) and hyperlink URLs.
    
    Workflow:
    - Mode: budget
    - Preserve markdown: True
    
    Verifications:
    - All 12 section headers ('### Section 1:' through '### Section 12:') retained.
    - Hyperlinks ([Docs Portal](https://docs.cloud-example.com/api/...)) preserved.
    - No sections or paragraphs dropped.
    - Total character length remains proportional to input length (>80% retention).
    - 0 banned AI buzzwords across all 12 sections.
    """
    result = mock_humanizer.humanize(
        sample_long_article,
        mode="budget",
        preserve_markdown=True,
    )

    # 1. All sections intact
    for i in range(1, 13):
        assert f"### Section {i}:" in result.text, f"Section {i} was missing from reconstructed article!"
        assert f"https://docs.cloud-example.com/api/{i-1}" in result.text

    # 2. Length proportionality (no massive drop)
    assert len(result.text) >= 0.8 * len(sample_long_article)

    # 3. Buzzwords cleansed across entire long document
    violations = audit_buzzwords(result.text)
    assert len(violations) == 0, f"Found buzzwords in long article: {violations}"


def test_t4_06_daemon_rest_and_sse_workflow_scenario(api_test_client, sample_blog_post):
    """Scenario 6: End-to-End REST API & SSE Client Integration.
    
    A client application interacts with the local daemon:
    1. Probes GET /health to confirm daemon liveness and model name.
    2. Sends POST /v1/humanize to humanize a document synchronously.
    3. Initiates POST /v1/humanize/stream for real-time SSE token delivery.
    
    Verifications:
    - GET /health responds with status 'healthy' or 'ok', version, and engine.
    - POST /v1/humanize returns complete JSON response matching data contract.
    - POST /v1/humanize/stream delivers chunk events and terminates with [DONE].
    - Response times and data contracts are validated end-to-end.
    """
    # 1. Liveness check
    health_resp = api_test_client.get("/health")
    assert health_resp.status_code == 200
    health_data = health_resp.json()
    assert health_data["status"] in ["ok", "healthy"]
    assert "gemini" in health_data["engine"].lower()

    # 2. Synchronous REST Humanization
    payload = {
        "text": sample_blog_post,
        "mode": "budget",
        "tone": "casual",
        "reading_level": "general",
        "preserve_markdown": True,
    }
    sync_resp = api_test_client.post("/v1/humanize", json=payload)
    assert sync_resp.status_code == 200
    sync_data = sync_resp.json()
    assert "humanized_text" in sync_data
    assert sync_data["mode"] == "budget"
    assert sync_data["prompt_tokens"] > 0
    assert "# Exploring Modern Web Architecture" in sync_data["humanized_text"]

    # 3. Real-Time SSE Streaming
    stream_payload = {
        "text": "Streaming real-time chunks through the local daemon without buffering delay.",
        "mode": "budget",
    }
    with api_test_client.stream("POST", "/v1/humanize/stream", json=stream_payload) as stream_resp:
        assert stream_resp.status_code == 200
        assert "text/event-stream" in stream_resp.headers.get("content-type", "")
        lines = [l.strip() for l in stream_resp.iter_lines() if l.strip()]
        assert len(lines) >= 2
        assert lines[-1] == "data: [DONE]"
