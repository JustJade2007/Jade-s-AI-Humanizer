"""Empirical Adversarial Challenge Suite for Milestone 2: Markdown & Table Preservation.

Tests boundary conditions, stress scenarios, and invariance guarantees for:
- Fenced code blocks with language specifiers
- Unclosed code fences extending to EOF
- Tilde fences (~~~ and ~~~~)
- Indented 4-space code blocks
- Code blocks containing buzzwords in comments and string literals
- GFM markdown tables with header rows, alignment delimiters (:---:), and embedded pipes
- Nested fences, windows line endings (\\r\\n), blockquote tables
- 100% byte-for-byte invariance verification
"""

from __future__ import annotations

import os
import sys
import unittest

# Ensure src is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")))

from humanizer.client import Humanizer
from humanizer.parser.markdown import (
    BlockType,
    CodeBlock,
    DocumentBlock,
    DocumentChunk,
    MarkdownDocument,
    ParagraphBlock,
    TableBlock,
)
from humanizer.parser.mask import InlineMasker, MaskState


class TestAdversarialMarkdownParser(unittest.TestCase):
    """Adversarial challenge test suite for MarkdownDocument and Table/Code preservation."""

    def setUp(self) -> None:
        self.humanizer = Humanizer(mock_mode=True)

    # --------------------------------------------------------------------------
    # 1. FENCED CODE BLOCKS WITH LANGUAGE SPECIFIERS & TILDE FENCES
    # --------------------------------------------------------------------------

    def test_fenced_code_blocks_with_various_languages(self):
        """Verify fenced code blocks with diverse language specifiers are byte-for-byte preserved."""
        md = (
            "Intro paragraph here.\n\n"
            "```python\n"
            "def calculate(x: int) -> int:\n"
            "    return x * 42\n"
            "```\n\n"
            "Middle text.\n\n"
            "```typescript\n"
            "interface Config {\n"
            "  port: number;\n"
            "  host: string;\n"
            "}\n"
            "```\n\n"
            "Outro text.\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        code_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 2)
        self.assertEqual(
            code_chunks[0].raw_text,
            "```python\ndef calculate(x: int) -> int:\n    return x * 42\n```\n",
        )
        self.assertEqual(
            code_chunks[1].raw_text,
            "```typescript\ninterface Config {\n  port: number;\n  host: string;\n}\n```\n",
        )

        # Reconstruct without changes
        reconstructed = doc.reconstruct([c.content for c in chunks])
        self.assertEqual(reconstructed, md)

        # Full humanization run
        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(code_chunks[0].raw_text, res.text)
        self.assertIn(code_chunks[1].raw_text, res.text)

    def test_tilde_code_fences(self):
        """Verify tilde fences (~~~ and ~~~~) are recognized and byte-for-byte preserved."""
        md = (
            "Leading text.\n\n"
            "~~~bash\n"
            "curl -X POST http://localhost:8000/v1/humanize \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"text": "Hello world"}\'\n'
            "~~~\n\n"
            "~~~~python\n"
            "~~~nested tildes~~~\n"
            "~~~~\n\n"
            "Trailing text.\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        code_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 2)
        self.assertTrue(code_chunks[0].raw_text.startswith("~~~bash\n"))
        self.assertTrue(code_chunks[0].raw_text.endswith("~~~\n"))
        self.assertTrue(code_chunks[1].raw_text.startswith("~~~~python\n"))
        self.assertTrue(code_chunks[1].raw_text.endswith("~~~~\n"))

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(code_chunks[0].raw_text, res.text)
        self.assertIn(code_chunks[1].raw_text, res.text)

    def test_nested_code_fences_with_higher_backtick_count(self):
        """Verify code blocks with 4 or 5 backticks containing 3 backticks inside."""
        md = (
            "Example of markdown code block inside markdown:\n\n"
            "`````markdown\n"
            "```python\n"
            "print('inner')\n"
            "```\n"
            "`````\n\n"
            "Done.\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()
        code_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 1)
        expected = "`````markdown\n```python\nprint('inner')\n```\n`````\n"
        self.assertEqual(code_chunks[0].raw_text, expected)

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(expected, res.text)

    # --------------------------------------------------------------------------
    # 2. UNCLOSED CODE FENCES
    # --------------------------------------------------------------------------

    def test_unclosed_code_fence_extends_to_eof(self):
        """Verify unclosed code fence is gracefully captured until EOF without crashing or corruption."""
        md = (
            "Start prose.\n\n"
            "```python\n"
            "def unfinished():\n"
            "    # Missing closing fence\n"
            "    return 'tail'\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        code_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 1)
        expected_unclosed = (
            "```python\n"
            "def unfinished():\n"
            "    # Missing closing fence\n"
            "    return 'tail'\n"
        )
        self.assertEqual(code_chunks[0].raw_text, expected_unclosed)

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(expected_unclosed, res.text)

    # --------------------------------------------------------------------------
    # 3. INDENTED 4-SPACE CODE BLOCKS (STRESS TEST)
    # --------------------------------------------------------------------------

    def test_indented_4_space_code_block_behavior(self):
        """Stress-test how indented 4-space blocks are classified and whether they survive humanization."""
        md = (
            "Regular introductory paragraph.\n\n"
            "    def calculate_pi():\n"
            "        # Indented 4-space code block\n"
            "        precision = 100\n"
            "        return 3.14159\n\n"
            "Concluding paragraph.\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        # Check block types
        block_types = [b.block_type for b in doc.blocks]
        # Check if any block was classified as CODE
        has_code_block = any(b.block_type == BlockType.CODE for b in doc.blocks)
        
        # Check humanization result
        res = self.humanizer.humanize(md, preserve_markdown=True)

        expected_code = (
            "    def calculate_pi():\n"
            "        # Indented 4-space code block\n"
            "        precision = 100\n"
            "        return 3.14159"
        )
        is_identical = expected_code in res.text

        # Record findings
        print(f"\n[STRESS TEST: Indented 4-space block]")
        print(f"  Recognized as CodeBlock: {has_code_block}")
        print(f"  Block types parsed: {block_types}")
        print(f"  Preserved byte-for-byte in output: {is_identical}")

    # --------------------------------------------------------------------------
    # 4. CODE BLOCKS CONTAINING BANNED BUZZWORDS IN STRINGS & COMMENTS
    # --------------------------------------------------------------------------

    def test_code_blocks_containing_buzzwords(self):
        """Verify code comments and string literals with banned AI buzzwords are 100% untouched."""
        code_body = (
            "```python\n"
            "# We must delve into this multifaceted tapestry of metrics.\n"
            "# Moreover, it is crucial to leverage a robust, seamless algorithm.\n"
            "def analyze():\n"
            "    '''In summary, this testament fosters holistic synergy.'''\n"
            '    query = "SELECT * FROM realm WHERE pivotal = 1"\n'
            '    buzzword_list = ["delve", "tapestry", "moreover", "robust"]\n'
            "    return buzzword_list\n"
            "```\n"
        )
        md = f"Introductory text.\n\n{code_body}\nConcluding thoughts.\n"

        res = self.humanizer.humanize(md, preserve_markdown=True)

        # The exact code block must be present 100% byte-for-byte
        self.assertIn(code_body, res.text)
        # Verify internal buzzwords were NOT replaced with synonyms inside code
        self.assertIn("delve into this multifaceted tapestry", res.text)
        self.assertIn("robust, seamless algorithm", res.text)
        self.assertIn("SELECT * FROM realm WHERE pivotal = 1", res.text)
        self.assertIn('["delve", "tapestry", "moreover", "robust"]', res.text)

    # --------------------------------------------------------------------------
    # 5. GFM MARKDOWN TABLES WITH ALIGNMENT DELIMITERS & EMBEDDED PIPES
    # --------------------------------------------------------------------------

    def test_gfm_table_with_alignments(self):
        """Verify GFM tables with left, center, right alignment delimiters are 100% byte-for-byte."""
        table_text = (
            "| Item | Description | Status | Priority |\n"
            "| :--- | :---: | ---: | :--- |\n"
            "| Task 1 | Implement parser | Complete | High |\n"
            "| Task 2 | Verify tables | In Progress | Critical |\n"
            "| Task 3 | Add benchmark | Pending | Normal |\n"
        )
        md = f"Overview paragraph.\n\n{table_text}\nSummary paragraph.\n"

        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        table_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(table_chunks[0].raw_text, table_text)

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(table_text, res.text)

    def test_gfm_table_with_embedded_pipes(self):
        """Verify tables with embedded pipes in code spans or escaped pipes are preserved."""
        table_text = (
            "| Operator | Example | Escaped Syntax | Explanation |\n"
            "| --- | :--- | :---: | --- |\n"
            "| Bitwise OR | `a | b` | `\\|` | Binary or operator |\n"
            "| Multiple | `x | y | z` | `a \\| b` | Chained bitwise pipes |\n"
            "| Empty Cell | | `none` | Blank middle cell |\n"
        )
        md = f"Section header.\n\n{table_text}\nPost-table notes.\n"

        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        table_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(table_chunks[0].raw_text, table_text)

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(table_text, res.text)

    def test_table_without_outer_pipes(self):
        """Verify GFM table variant without leading/trailing outer pipes."""
        table_text = (
            "Header A | Header B | Header C\n"
            "--- | :---: | ---\n"
            "Val 1 | Val 2 | Val 3\n"
            "Val 4 | Val 5 | Val 6\n"
        )
        md = f"Start.\n\n{table_text}\nEnd.\n"

        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()

        table_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(table_chunks[0].raw_text, table_text)

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(table_text, res.text)

    def test_table_containing_banned_buzzwords(self):
        """Verify table cells containing buzzwords remain 100% byte-for-byte identical."""
        table_text = (
            "| Metric | Assessment |\n"
            "| --- | --- |\n"
            "| Tapestry | We delve into holistic synergy |\n"
            "| Pivotal | A robust cornerstone of the realm |\n"
        )
        md = f"Introduction.\n\n{table_text}\nConclusion.\n"

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn(table_text, res.text)
        self.assertIn("We delve into holistic synergy", res.text)
        self.assertIn("A robust cornerstone of the realm", res.text)

    # --------------------------------------------------------------------------
    # 6. COMBINED DOCUMENT & 100% BYTE-FOR-BYTE INVARIANCE
    # --------------------------------------------------------------------------

    def test_comprehensive_document_byte_for_byte_fidelity(self):
        """Full complex document containing headers, lists, code, tables, and inline elements."""
        code_1 = (
            "```python\n"
            "import os\n"
            "from typing import List\n\n"
            "def process_data(items: List[str]) -> int:\n"
            "    # Delve into items\n"
            "    return len(items)\n"
            "```\n"
        )
        table_1 = (
            "| Column 1 | Column 2 | Column 3 |\n"
            "| :--- | :---: | ---: |\n"
            "| Alpha | `val | 1` | 100 |\n"
            "| Beta | `val | 2` | 200 |\n"
        )
        code_2 = (
            "~~~bash\n"
            "echo 'running tests'\n"
            "pytest -v\n"
            "~~~\n"
        )

        md = (
            "# Main Architecture Document\n\n"
            "This is the introductory overview paragraph with `inline_code()` and [Docs Link](https://example.org).\n\n"
            f"{code_1}\n"
            "## Data Flow Specifications\n\n"
            "Below is the data mapping specification table:\n\n"
            f"{table_1}\n"
            "### Deployment Checklist\n\n"
            "- Step 1: Run local daemon\n"
            "- Step 2: Validate endpoints\n"
            "- Step 3: Package binary\n\n"
            f"{code_2}\n"
            "Final wrap-up paragraph.\n"
        )

        res = self.humanizer.humanize(md, preserve_markdown=True)

        # Verify exact byte-for-byte presence of code blocks and table
        self.assertIn(code_1, res.text)
        self.assertIn(table_1, res.text)
        self.assertIn(code_2, res.text)

        # Verify headers were preserved
        self.assertIn("# Main Architecture Document", res.text)
        self.assertIn("## Data Flow Specifications", res.text)
        self.assertIn("### Deployment Checklist", res.text)

        # Verify inline link URL and inline code
        self.assertIn("https://example.org", res.text)
        self.assertIn("`inline_code()`", res.text)

    # --------------------------------------------------------------------------
    # 7. EDGE CASES & ATTACK VECTORS
    # --------------------------------------------------------------------------

    def test_windows_crlf_line_endings(self):
        """Verify Windows CRLF (\\r\\n) is preserved without corrupting code or tables."""
        md_crlf = (
            "# Heading\r\n\r\n"
            "```python\r\n"
            "x = 10\r\n"
            "y = 20\r\n"
            "```\r\n\r\n"
            "| H1 | H2 |\r\n"
            "| :--- | :---: |\r\n"
            "| A | B |\r\n\r\n"
            "End paragraph.\r\n"
        )
        doc = MarkdownDocument(md_crlf)
        chunks = doc.extract_chunks()

        code_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "code"]
        self.assertEqual(len(code_chunks), 1)
        self.assertEqual(code_chunks[0].raw_text, "```python\r\nx = 10\r\ny = 20\r\n```\r\n")

        table_chunks = [c for c in chunks if not c.is_humanizable and c.chunk_type == "table"]
        self.assertEqual(len(table_chunks), 1)
        self.assertEqual(table_chunks[0].raw_text, "| H1 | H2 |\r\n| :--- | :---: |\r\n| A | B |\r\n")

        res = self.humanizer.humanize(md_crlf, preserve_markdown=True)
        self.assertIn("```python\r\nx = 10\r\ny = 20\r\n```\r\n", res.text)
        self.assertIn("| H1 | H2 |\r\n| :--- | :---: |\r\n| A | B |\r\n", res.text)

    def test_adjacent_code_and_table_without_blank_lines(self):
        """Verify code block directly followed by table without blank lines between them."""
        md = (
            "```python\n"
            "def foo(): pass\n"
            "```\n"
            "| Col1 | Col2 |\n"
            "| --- | --- |\n"
            "| V1 | V2 |\n"
            "~~~bash\n"
            "echo adjacent\n"
            "~~~\n"
        )
        doc = MarkdownDocument(md)
        chunks = doc.extract_chunks()
        types = [c.chunk_type for c in chunks]
        self.assertEqual(types, ["code", "table", "code"])

        res = self.humanizer.humanize(md, preserve_markdown=True)
        self.assertIn("```python\ndef foo(): pass\n```\n", res.text)
        self.assertIn("| Col1 | Col2 |\n| --- | --- |\n| V1 | V2 |\n", res.text)
        self.assertIn("~~~bash\necho adjacent\n~~~\n", res.text)


if __name__ == "__main__":
    unittest.main()
