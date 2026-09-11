"""Comprehensive unit tests for Markdown block parser, semantic chunker, and inline masker."""

from __future__ import annotations

import asyncio
import pytest

from humanizer import Humanizer, HumanizeResult
from humanizer.parser.markdown import (
    BlankLineBlock,
    BlockType,
    CodeBlock,
    DocumentBlock,
    DocumentChunk,
    HeaderBlock,
    ListItemBlock,
    MarkdownDocument,
    ParagraphBlock,
    QuoteBlock,
    SeparatorBlock,
    TableBlock,
)
from humanizer.parser.mask import (
    InlineMasker,
    MaskState,
    mask_inline_tokens,
    unmask_inline_tokens,
)


# ==============================================================================
# 1. INLINE MASKER UNIT TESTS
# ==============================================================================

def test_inline_code_masking_and_unmasking():
    """Test inline backtick code is protected with ⟦INLINE_CODE_X⟧ and restored bit-for-bit."""
    text = "Use `def process()` and ``items = [1, 2]`` to run the service."
    masked, state = InlineMasker.mask(text)

    assert "⟦INLINE_CODE_0⟧" in masked
    assert "⟦INLINE_CODE_1⟧" in masked
    assert "`def process()`" not in masked
    assert len(state.inline_codes) == 2
    assert state.inline_codes[0] == "`def process()`"
    assert state.inline_codes[1] == "``items = [1, 2]``"

    unmasked = InlineMasker.unmask(masked, state)
    assert unmasked == text


def test_markdown_link_masking_and_unmasking():
    """Test markdown links have only target URL masked, leaving anchor accessible."""
    text = "Refer to [Documentation Guide](https://example.com/docs?id=42#section) for details."
    masked, state = InlineMasker.mask(text)

    assert "[Documentation Guide](⟦URL_0⟧)" in masked
    assert "https://example.com" not in masked
    assert len(state.urls) == 1
    assert state.urls[0] == "https://example.com/docs?id=42#section"

    # Simulate anchor rewrite
    modified = masked.replace("[Documentation Guide]", "[the official guide]")
    unmasked = InlineMasker.unmask(modified, state)
    assert unmasked == "Refer to [the official guide](https://example.com/docs?id=42#section) for details."


def test_autolink_and_bare_url_masking():
    """Test autolinks <https://...> and bare URLs are protected."""
    text = "Contact <support@example.com> or visit https://ai.example.org/api directly."
    masked, state = InlineMasker.mask(text)

    assert "⟦URL_0⟧" in masked
    assert "⟦URL_1⟧" in masked
    assert "https://ai.example.org" not in masked

    unmasked = InlineMasker.unmask(masked, state)
    assert unmasked == text


def test_math_formula_masking():
    """Test display and inline math formulas are masked with ⟦MATH_X⟧."""
    text = "Formula: $O(\\log n)$ and display: $$\\sum_{i=1}^n x_i$$ are formal."
    masked, state = InlineMasker.mask(text)

    assert "⟦MATH_0⟧" in masked
    assert "⟦MATH_1⟧" in masked
    assert len(state.math_formulas) == 2

    unmasked = InlineMasker.unmask(masked, state)
    assert unmasked == text


def test_inline_unmasking_resilience_to_whitespace():
    """Test unmasking recovers placeholders with minor LLM whitespace changes."""
    text = "Here is `some_code()`."
    masked, state = InlineMasker.mask(text)

    # LLM added spaces inside sentinel brackets
    mutated = masked.replace("⟦INLINE_CODE_0⟧", "⟦ INLINE_CODE_0 ⟧")
    unmasked = InlineMasker.unmask(mutated, state)
    assert unmasked == "Here is `some_code()`."


def test_functional_mask_helpers():
    """Test functional mask_inline_tokens and unmask_inline_tokens convenience wrappers."""
    text = "Run `git status` then check https://git-scm.com."
    masked, token_map = mask_inline_tokens(text)
    assert len(token_map) == 2
    unmasked = unmask_inline_tokens(masked, token_map)
    assert unmasked == text


# ==============================================================================
# 2. TWO-TIER BLOCK PARSER UNIT TESTS
# ==============================================================================

def test_code_block_parsing_and_invariance():
    """Test fenced code blocks are separated as immutable CodeBlock instances."""
    doc_text = (
        "Introductory prose paragraph.\n\n"
        "```python\n"
        "def compute_hash(data: bytes) -> str:\n"
        "    import hashlib\n"
        "    return hashlib.sha256(data).hexdigest()\n"
        "```\n\n"
        "Trailing prose paragraph."
    )
    doc = MarkdownDocument(doc_text)
    assert len(doc.blocks) == 5

    assert isinstance(doc.blocks[0], ParagraphBlock)
    assert doc.blocks[0].is_humanizable is True

    assert isinstance(doc.blocks[1], BlankLineBlock)
    assert doc.blocks[1].is_humanizable is False

    code_block = doc.blocks[2]
    assert isinstance(code_block, CodeBlock)
    assert code_block.is_humanizable is False
    assert code_block.language == "python"
    assert "def compute_hash" in code_block.code
    assert code_block.raw_text == (
        "```python\n"
        "def compute_hash(data: bytes) -> str:\n"
        "    import hashlib\n"
        "    return hashlib.sha256(data).hexdigest()\n"
        "```\n"
    )

    assert isinstance(doc.blocks[3], BlankLineBlock)
    assert isinstance(doc.blocks[4], ParagraphBlock)

    # Lossless reconstruction
    assert "".join(b.raw_text for b in doc.blocks) == doc_text


def test_tilde_code_block_parsing():
    """Test ~~~ fenced code blocks are parsed properly."""
    doc_text = "~~~bash\necho 'hello world'\n~~~\n"
    doc = MarkdownDocument(doc_text)
    assert len(doc.blocks) == 1
    assert isinstance(doc.blocks[0], CodeBlock)
    assert doc.blocks[0].language == "bash"
    assert doc.blocks[0].fence_char == "~"
    assert doc.blocks[0].raw_text == doc_text


def test_markdown_table_parsing():
    """Test GFM tables are parsed as immutable TableBlock instances."""
    table_text = (
        "| Service | Latency (ms) | Throughput |\n"
        "| :--- | :--- | :--- |\n"
        "| Auth | 15 | 4500 |\n"
        "| DB | 8 | 12000 |\n"
    )
    doc_text = f"Overview:\n\n{table_text}\nSummary note."
    doc = MarkdownDocument(doc_text)

    # Find the table block
    tables = [b for b in doc.blocks if isinstance(b, TableBlock)]
    assert len(tables) == 1
    tb = tables[0]
    assert tb.is_humanizable is False
    assert tb.raw_text == table_text
    assert "".join(b.raw_text for b in doc.blocks) == doc_text


def test_atx_header_parsing_and_prefixes():
    """Test ATX headers of levels 1 to 6 are parsed with prefixes and content."""
    doc_text = (
        "# Main Title\n\n"
        "## Sub Heading\n\n"
        "### Section 1.1\n\n"
        "###### Deep Heading\n"
    )
    doc = MarkdownDocument(doc_text)
    headers = [b for b in doc.blocks if isinstance(b, HeaderBlock)]

    assert len(headers) == 4
    assert headers[0].level == 1
    assert headers[0].prefix == "# "
    assert headers[0].content == "Main Title"

    assert headers[1].level == 2
    assert headers[1].prefix == "## "
    assert headers[1].content == "Sub Heading"

    assert headers[2].level == 3
    assert headers[2].prefix == "### "
    assert headers[2].content == "Section 1.1"

    assert headers[3].level == 6
    assert headers[3].prefix == "###### "
    assert headers[3].content == "Deep Heading"


def test_list_items_unordered_and_ordered():
    """Test unordered and ordered list items with markers and indentation."""
    doc_text = (
        "- Item Alpha\n"
        "- Item Beta\n"
        "  - Nested Alpha\n"
        "1. First Step\n"
        "2. Second Step\n"
    )
    doc = MarkdownDocument(doc_text)
    items = [b for b in doc.blocks if isinstance(b, ListItemBlock)]
    assert len(items) == 5

    assert items[0].marker == "-"
    assert items[0].content == "Item Alpha"

    assert items[1].marker == "-"
    assert items[1].content == "Item Beta"

    assert items[2].marker == "-"
    assert items[2].indent == "  "
    assert items[2].content == "Nested Alpha"

    assert items[3].marker == "1."
    assert items[3].content == "First Step"

    assert items[4].marker == "2."
    assert items[4].content == "Second Step"


def test_blockquotes_and_horizontal_rules():
    """Test blockquotes and thematic breaks / separators."""
    doc_text = (
        "> Quoted inspiration line\n\n"
        "---\n\n"
        "***\n"
    )
    doc = MarkdownDocument(doc_text)
    quotes = [b for b in doc.blocks if isinstance(b, QuoteBlock)]
    assert len(quotes) == 1
    assert quotes[0].prefix == "> "
    assert quotes[0].content == "Quoted inspiration line"

    separators = [b for b in doc.blocks if isinstance(b, SeparatorBlock)]
    assert len(separators) == 2
    assert separators[0].raw_text == "---\n"
    assert separators[1].raw_text == "***\n"


# ==============================================================================
# 3. SEMANTIC CHUNKING & RECONSTRUCTION UNIT TESTS
# ==============================================================================

def test_semantic_chunking_immutable_isolation():
    """Test code blocks and tables are never merged into prose chunks."""
    doc_text = (
        "Prose section 1.\n\n"
        "```python\nx = 1\n```\n\n"
        "Prose section 2.\n\n"
        "| Col1 | Col2 |\n|---|---|\n| A | B |\n\n"
        "Prose section 3."
    )
    doc = MarkdownDocument(doc_text)
    chunks = doc.extract_chunks(max_chunk_chars=1500)

    # Verify immutable blocks are separate chunks
    code_chunks = [c for c in chunks if c.chunk_type == "code"]
    table_chunks = [c for c in chunks if c.chunk_type == "table"]

    assert len(code_chunks) == 1
    assert code_chunks[0].is_humanizable is False
    assert code_chunks[0].content == "```python\nx = 1\n```\n"

    assert len(table_chunks) == 1
    assert table_chunks[0].is_humanizable is False
    assert "| Col1 | Col2 |" in table_chunks[0].content

    # Lossless reconstruction round-trip test
    reconstructed = doc.reconstruct([c.content for c in chunks])
    assert reconstructed == doc_text


def test_semantic_chunking_oversized_paragraph_split():
    """Test oversized single paragraph is partitioned along sentence boundaries."""
    sent1 = "The first sentence describes the system architecture in substantial detail."
    sent2 = "The second sentence explains how the load balancer coordinates traffic."
    sent3 = "The third sentence covers database failover and replica synchronization."
    sent4 = "The fourth sentence summarizes monitoring and operational alerting metrics."
    long_para = f"{sent1} {sent2} {sent3} {sent4}"

    doc = MarkdownDocument(long_para)
    # Set max_chunk_chars low enough to force sentence partitioning (~100 chars)
    chunks = doc.extract_chunks(max_chunk_chars=160)

    assert len(chunks) > 1
    for c in chunks:
        assert c.is_humanizable is True
        # No sentence should be bisected mid-word
        for s in [sent1, sent2, sent3, sent4]:
            if s[:20] in c.content:
                assert s in c.content


def test_long_article_chunking_section_coherence():
    """Test multi-page document with 12 sections is cleanly partitioned at headers."""
    sections = []
    for i in range(12):
        sections.append(
            f"### Section {i+1}: Advanced Systems\n\n"
            f"Paragraph describing architectural aspects of section {i+1}. "
            f"Components must maintain high throughput under load."
        )
    article = "\n\n".join(sections)
    doc = MarkdownDocument(article)
    chunks = doc.extract_chunks(max_chunk_chars=500)

    assert len(chunks) >= 6
    # Verify reconstruction
    reconstructed = doc.reconstruct([c.content for c in chunks])
    assert reconstructed == article


def test_selective_chunk_reconstruction():
    """Test reconstructing when passing only humanizable chunks or modified texts."""
    doc_text = (
        "# Title\n\n"
        "Original first paragraph.\n\n"
        "```python\n"
        "preserved_code()\n"
        "```\n\n"
        "Original second paragraph."
    )
    doc = MarkdownDocument(doc_text)
    chunks = doc.extract_chunks()

    # Pass only humanized text for humanizable chunks
    humanized_pieces = []
    for c in chunks:
        if c.is_humanizable:
            humanized_pieces.append(c.content.replace("Original", "Humanized"))

    reconstructed = doc.reconstruct(humanized_pieces)
    assert "Humanized first paragraph." in reconstructed
    assert "Humanized second paragraph." in reconstructed
    assert "```python\npreserved_code()\n```" in reconstructed


# ==============================================================================
# 4. HUMANIZER CLIENT INTEGRATION TESTS
# ==============================================================================

def test_client_humanize_markdown_table_and_code_preservation():
    """Verify Humanizer.humanize with preserve_markdown preserves tables and code 100%."""
    client = Humanizer(mock_mode=True)
    doc = (
        "# Architecture Document\n\n"
        "Moreover, we must delve into system performance benchmarks:\n\n"
        "| Service | Target Latency | Actual Latency |\n"
        "| :--- | :--- | :--- |\n"
        "| Cache | < 5ms | 2ms |\n"
        "| Query | < 50ms | 28ms |\n\n"
        "```python\n"
        "# We must delve into this logic\n"
        "def fetch():\n"
        "    return 'tapestry'\n"
        "```\n\n"
        "In summary, all service latency numbers satisfy our requirements."
    )
    res = client.humanize(doc, preserve_markdown=True)

    # 1. ATX Header preserved
    assert "# Architecture Document" in res.text

    # 2. Table preserved 100% byte-for-byte
    assert "| Service | Target Latency | Actual Latency |" in res.text
    assert "| :--- | :--- | :--- |" in res.text
    assert "| Cache | < 5ms | 2ms |" in res.text
    assert "| Query | < 50ms | 28ms |" in res.text

    # 3. Code block preserved 100% byte-for-byte including comments and strings
    expected_code = (
        "```python\n"
        "# We must delve into this logic\n"
        "def fetch():\n"
        "    return 'tapestry'\n"
        "```"
    )
    assert expected_code in res.text

    # 4. Prose buzzwords purged
    assert "Moreover," not in res.text
    assert "In summary," not in res.text


def test_client_humanize_inline_code_and_url_preservation():
    """Verify Humanizer.humanize preserves inline `code` and markdown links."""
    client = Humanizer(mock_mode=True)
    doc = (
        "Execute `from humanizer import Humanizer` in your script. "
        "Moreover, review [Documentation](https://humanizer.local/v1/api) for details."
    )
    res = client.humanize(doc, preserve_markdown=True)

    assert "`from humanizer import Humanizer`" in res.text
    assert "https://humanizer.local/v1/api" in res.text
    assert "Moreover," not in res.text


@pytest.mark.asyncio
async def test_client_humanize_async_with_markdown():
    """Verify Humanizer.humanize_async with preserve_markdown preserves structure."""
    client = Humanizer(mock_mode=True)
    doc = (
        "## Database Schema\n\n"
        "- Index on `user_id`\n"
        "- Foreign key on `account_id`\n\n"
        "```sql\n"
        "CREATE INDEX idx_user ON users(user_id);\n"
        "```"
    )
    res = await client.humanize_async(doc, preserve_markdown=True)

    assert "## Database Schema" in res.text
    assert "- " in res.text
    assert "`user_id`" in res.text
    assert "```sql\nCREATE INDEX idx_user ON users(user_id);\n```" in res.text


@pytest.mark.asyncio
async def test_client_humanize_stream_markdown():
    """Verify Humanizer.humanize_stream delivers chunked markdown with code blocks."""
    client = Humanizer(mock_mode=True)
    doc = (
        "### Pipeline Status\n\n"
        "Processing requests.\n\n"
        "```python\n"
        "status = 'ok'\n"
        "```\n\n"
        "End of report."
    )
    chunks = []
    async for chunk in client.humanize_stream(doc, preserve_markdown=True):
        chunks.append(chunk)

    full_output = "".join(chunks)
    assert "### Pipeline Status" in full_output
    assert "```python\nstatus = 'ok'\n```" in full_output
    assert "End of report." in full_output


def test_client_humanize_stream_sync_markdown():
    """Verify synchronous streaming delivers intact markdown."""
    client = Humanizer(mock_mode=True)
    doc = (
        "# Overview\n\n"
        "Test text for sync stream.\n\n"
        "```python\nx = 1\n```"
    )
    chunks = list(client.humanize_stream_sync(doc, preserve_markdown=True))
    full_output = "".join(chunks)

    assert "# Overview" in full_output
    assert "```python\nx = 1\n```" in full_output
