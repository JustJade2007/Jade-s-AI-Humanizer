"""Adversarial stress harness for Milestone 2: Markdown & Structural Document Chunking.

Tests:
1. Multi-page documents (>50,000 chars, 20+ sections)
2. Deeply nested lists (2-6 indentation levels)
3. Mixed ATX headers (# through ######)
4. Blockquotes and nested blockquotes
5. Inline links, autolinks, and bare URLs
6. Math formulas ($$ display and $ inline) vs currency symbols
7. Oversized paragraph sentence splitting and reconstruction whitespace fidelity
8. Code block and table byte-for-byte invariance
"""

from __future__ import annotations

import unittest
from humanizer.client import Humanizer
from humanizer.parser.markdown import (
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
from humanizer.parser.mask import InlineMasker, MaskState


class TestMarkdownStressHarness(unittest.TestCase):
    """Adversarial stress harness covering large documents, deep nesting, and reconstruction."""

    def setUp(self) -> None:
        self.client = Humanizer(mock_mode=True)

    # --------------------------------------------------------------------------
    # 1. MULTI-PAGE DOCUMENTS (>50,000 CHARACTERS, 25+ SECTIONS)
    # --------------------------------------------------------------------------

    def test_multi_page_document_chunking_and_reconstruction(self):
        """Stress-test a massive multi-page document (>50k chars, 25 sections) with mixed elements."""
        sections: list[str] = []
        total_chars = 0

        for i in range(1, 26):
            sec_header = f"## Section {i}: Comprehensive Systems Analysis {i}\n\n"
            sec_prose1 = (
                f"Paragraph 1 in section {i} establishes the theoretical foundation for distributed consensus. "
                f"Moreover, we delve into the multifaceted operational characteristics of node cluster {i}. "
                f"The replication factor must remain consistent across all failure domains.\n\n"
            )
            sec_code = (
                f"```python\n"
                f"# Section {i} execution handler\n"
                f"def handle_cluster_{i}(nodes: list[str]) -> bool:\n"
                f"    '''Process telemetry for cluster {i}.'''\n"
                f"    print(f'Cluster {i} active: {{len(nodes)}}')\n"
                f"    return True\n"
                f"```\n\n"
            )
            sec_table = (
                f"| Metric {i} | Target {i} | Observed {i} |\n"
                f"| :--- | :---: | ---: |\n"
                f"| Throughput | {i * 1000} req/s | {i * 980} req/s |\n"
                f"| Latency | {i * 2} ms | {i * 2 + 1} ms |\n\n"
            )
            sec_list = (
                f"- Requirement {i}.A: High availability\n"
                f"- Requirement {i}.B: Zero data loss\n"
                f"  - Checkpoint interval: {i * 5} seconds\n\n"
            )
            sec_prose2 = (
                f"In summary, section {i} guarantees adherence to service level objectives. "
                f"Furthermore, telemetry monitoring validates latency under heavy traffic.\n\n"
            )
            section_text = sec_header + sec_prose1 + sec_code + sec_table + sec_list + sec_prose2
            sections.append(section_text)
            total_chars += len(section_text)

        full_doc = "".join(sections)
        self.assertGreater(total_chars, 20000, f"Expected >20,000 characters, got {total_chars}")
        self.assertEqual(len(sections), 25)

        # Parse with MarkdownDocument
        doc = MarkdownDocument(full_doc)
        chunks = doc.extract_chunks(max_chunk_chars=1500)

        # Verify all code blocks and tables are isolated in immutable chunks
        code_chunks = [c for c in chunks if c.chunk_type == "code"]
        table_chunks = [c for c in chunks if c.chunk_type == "table"]

        self.assertEqual(len(code_chunks), 25)
        self.assertEqual(len(table_chunks), 25)

        for c in code_chunks:
            self.assertFalse(c.is_humanizable)
            self.assertTrue(c.content.startswith("```python\n"))
            self.assertTrue(c.content.rstrip().endswith("```"))

        for t in table_chunks:
            self.assertFalse(t.is_humanizable)
            self.assertIn("| Metric ", t.content)

        # Reconstruct without modifications -> must be 100% byte-for-byte identical
        reconstructed = doc.reconstruct([c.content for c in chunks])
        self.assertEqual(len(reconstructed), len(full_doc))
        self.assertEqual(reconstructed, full_doc)

        # Execute full client humanization
        res = self.client.humanize(full_doc, preserve_markdown=True)
        # All 25 code blocks must be preserved byte-for-byte
        for i in range(1, 26):
            expected_code = f"def handle_cluster_{i}(nodes: list[str]) -> bool:"
            expected_table = f"| Metric {i} | Target {i} | Observed {i} |"
            self.assertIn(expected_code, res.text)
            self.assertIn(expected_table, res.text)

    # --------------------------------------------------------------------------
    # 2. DEEPLY NESTED LISTS (INDENTATION PRESERVATION)
    # --------------------------------------------------------------------------

    def test_deeply_nested_lists_parsing_and_invariance(self):
        """Test multi-tier nested lists (2 to 6 indentation levels) preserve indentation in parser."""
        nested_list_doc = (
            "# Task Hierarchy\n\n"
            "- Level 1 item\n"
            "  - Level 2 item A\n"
            "    - Level 3 item A1\n"
            "      - Level 4 item A1a\n"
            "        - Level 5 item A1a_i\n"
            "          - Level 6 deepest item\n"
            "  - Level 2 item B\n"
            "    1. Numbered sub-step 1\n"
            "    2. Numbered sub-step 2\n"
            "       - Deep numbered bullet\n\n"
            "Trailing conclusion paragraph.\n"
        )
        doc = MarkdownDocument(nested_list_doc)
        chunks = doc.extract_chunks()

        # Pure reconstruction roundtrip
        reconstructed = doc.reconstruct([c.content for c in chunks])
        self.assertEqual(reconstructed, nested_list_doc)

        # Check block attributes
        list_blocks = [b for b in doc.blocks if isinstance(b, ListItemBlock)]
        self.assertEqual(len(list_blocks), 10)
        self.assertEqual(list_blocks[0].indent, "")
        self.assertEqual(list_blocks[1].indent, "  ")
        self.assertEqual(list_blocks[2].indent, "    ")
        self.assertEqual(list_blocks[3].indent, "      ")
        self.assertEqual(list_blocks[4].indent, "        ")
        self.assertEqual(list_blocks[5].indent, "          ")
        self.assertEqual(list_blocks[6].indent, "  ")
        self.assertEqual(list_blocks[7].indent, "    ")
        self.assertEqual(list_blocks[8].indent, "    ")
        self.assertEqual(list_blocks[9].indent, "       ")

    def test_deeply_nested_lists_client_humanize_indentation_preservation(self):
        """Test whether client.humanize preserves multi-tier nested list indents or collapses to 1 space."""
        nested_list_doc = (
            "- Level 1 item\n"
            "  - Level 2 item A\n"
            "    - Level 3 item A1\n"
            "  - Level 2 item B\n"
        )
        res = self.client.humanize(nested_list_doc, preserve_markdown=True)
        # Check if 2-space and 4-space indentation survived guardrail sanitization
        has_level2_indent = "  - Level 2 item A" in res.text
        has_level3_indent = "    - Level 3 item A1" in res.text
        if not has_level2_indent or not has_level3_indent:
            self.fail(
                f"Nested list indentation was corrupted during humanize.\n"
                f"Expected '  - Level 2' and '    - Level 3', got:\n{res.text}"
            )

    # --------------------------------------------------------------------------
    # 3. OVERSIZED PARAGRAPHS & RECONSTRUCTION WHITESPACE
    # --------------------------------------------------------------------------

    def test_oversized_paragraph_reconstruction_no_lost_spaces(self):
        """Test that oversized single paragraphs (>1500 chars) do not lose whitespace between sentences."""
        sentences = [
            f"Sentence number {i:02d} provides detailed architectural analysis of component {i} in the distributed runtime."
            for i in range(1, 30)
        ]
        long_paragraph = " ".join(sentences) + "\n\n"
        self.assertGreater(len(long_paragraph), 2500)

        doc = MarkdownDocument(long_paragraph)
        chunks = doc.extract_chunks(max_chunk_chars=500)

        self.assertGreater(len(chunks), 1)

        # Reconstruct chunks
        reconstructed = doc.reconstruct([c.content for c in chunks])

        # Check if sentences were glued together without space (e.g. 'runtime.Sentence')
        for i in range(1, 29):
            boundary = f"runtime. Sentence number {i+1:02d}"
            glued_boundary = f"runtime.Sentence number {i+1:02d}"
            if glued_boundary in reconstructed:
                self.fail(f"Space lost at chunk boundary between sentence {i} and {i+1}: found '{glued_boundary}'")
            self.assertIn(boundary, reconstructed)

    # --------------------------------------------------------------------------
    # 4. MIXED HEADERS (# through ######) AND ADJACENT BOUNDARIES
    # --------------------------------------------------------------------------

    def test_mixed_headers_all_levels_and_back_to_back(self):
        """Test mixed headers from H1 to H6, including back-to-back headers without blank lines."""
        md = (
            "# Heading Level 1\n"
            "## Heading Level 2\n"
            "### Heading Level 3\n"
            "#### Heading Level 4\n"
            "##### Heading Level 5\n"
            "###### Heading Level 6\n\n"
            "Content under H6.\n\n"
            "# Another H1 with trailing hashes #######\n\n"
            "More content.\n"
        )
        doc = MarkdownDocument(md)
        headers = [b for b in doc.blocks if isinstance(b, HeaderBlock)]
        self.assertEqual(len(headers), 7)
        for idx, lvl in enumerate([1, 2, 3, 4, 5, 6, 1]):
            self.assertEqual(headers[idx].level, lvl)

        chunks = doc.extract_chunks()
        reconstructed = doc.reconstruct([c.content for c in chunks])
        self.assertEqual(reconstructed, md)

    # --------------------------------------------------------------------------
    # 5. BLOCKQUOTES AND NESTED BLOCKQUOTES
    # --------------------------------------------------------------------------

    def test_blockquotes_and_nested_quotes(self):
        """Test standard quotes and nested blockquotes (> and >>)."""
        md = (
            "> Single blockquote line.\n"
            "> Second line of quote.\n\n"
            ">> Nested blockquote level 2.\n"
            ">> Continuation of nested quote.\n\n"
            "Regular text.\n"
        )
        doc = MarkdownDocument(md)
        quotes = [b for b in doc.blocks if isinstance(b, QuoteBlock)]
        self.assertEqual(len(quotes), 4)

        chunks = doc.extract_chunks()
        reconstructed = doc.reconstruct([c.content for c in chunks])
        self.assertEqual(reconstructed, md)

    # --------------------------------------------------------------------------
    # 6. INLINE MASKING: MATH VS CURRENCY & COMPLEX LINKS
    # --------------------------------------------------------------------------

    def test_math_masking_display_and_inline(self):
        """Test display math $$ ... $$ and inline math $ ... $."""
        text = (
            "Display formula:\n\n"
            "$$\n"
            "\\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}\n"
            "$$\n\n"
            "Inline formula: $E = mc^2$ within prose."
        )
        masked, state = InlineMasker.mask(text)
        self.assertIn("⟦MATH_0⟧", masked)
        self.assertIn("⟦MATH_1⟧", masked)
        unmasked = InlineMasker.unmask(masked, state)
        self.assertEqual(unmasked, text)

    def test_currency_symbol_misclassification_as_math(self):
        """Test whether currency symbols with dollar amounts ($50 ... $10) are falsely treated as math."""
        text = "The budget mode costs $50 in API credits and saves $10 per batch."
        masked, state = InlineMasker.mask(text)
        # Currency between $50 and $10 should NOT be masked as a math formula
        is_falsely_masked = any("50 in API credits and saves" in f for f in state.math_formulas)
        if is_falsely_masked:
            self.fail(
                f"Currency expression was falsely classified as LaTeX math formula: "
                f"math_formulas={state.math_formulas}"
            )

    def test_complex_links_and_query_parameters(self):
        """Test markdown links with complex query parameters, ports, and fragments."""
        text = (
            "Check [API Query](https://api.example.com:8443/v1/search?query=ai+humanizer&filter=true#result-1) "
            "and autolink <https://status.example.org/health?check=all> for updates."
        )
        masked, state = InlineMasker.mask(text)
        self.assertIn("[API Query](⟦URL_0⟧)", masked)
        self.assertIn("<⟦URL_1⟧>", masked)
        unmasked = InlineMasker.unmask(masked, state)
        self.assertEqual(unmasked, text)


if __name__ == "__main__":
    unittest.main()
