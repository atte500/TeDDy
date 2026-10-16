from mistletoe import Document
from teddy_executor.core.services.parser_reporting import (
    _format_expected_structure,
    format_hybrid_ast_view,
    format_node_name,
)


def _get_token(markdown_str):
    doc = Document(markdown_str)
    return doc.children[0]


def test_format_node_name_code_fence_backticks():
    """Verify CodeFence with backticks is formatted correctly."""
    node = _get_token("```python\nline1\n```")
    # Expected: Code Block (3 backticks): "line1"
    name = format_node_name(node)
    assert "Code Block (3 backticks)" in name


def test_format_node_name_code_fence_tildes():
    """Verify CodeFence with tildes is formatted correctly."""
    node = _get_token("~~~~~~\ncontent\n~~~~~~")
    name = format_node_name(node)
    assert "Code Block (6 tildes)" in name


def test_format_node_name_block_code():
    """Verify indented BlockCode is labeled as such."""
    # Indented code block
    node = _get_token("    indented code")
    name = format_node_name(node)
    assert "Code Block (indented)" in name


def test_format_node_name_heading():
    """Verify Headings include their level."""
    node = _get_token("## Title")
    name = format_node_name(node)
    assert "Heading (Level 2)" in name


class TestParserReportingFenceBounding:
    """The parser-reporting embeds are bounded and byte-stable.

    `_format_expected_structure` and `format_hybrid_ast_view` route their embed
    through the shared `embed_in_fence` seam. The AST view caps every node
    preview at 60 characters, so a degenerate backtick run in a document cannot
    amplify the wrapper fence, while well-formed content keeps its exact bytes.
    """

    def test_expected_structure_is_byte_identical(self) -> None:
        assert _format_expected_structure() == (
            "### Expected Response Structure (MRP) \n"
            "```text\n"
            "[000] Heading (Level 1)\n"
            "[001] List (Metadata)\n"
            "[002] Heading (Level 2: Rationale)\n"
            "[003] Code Block (Rationale Content)\n"
            "[004] Heading (Level 2: Action Plan) —or— Heading (Level 2: Message)\n"
            "[005...] (If Action Plan) Heading (Level 3: Action Type) "
            "and (Action-specific AST nodes)\n"
            "```\n"
        )

    def test_ast_view_is_byte_identical(self) -> None:
        assert format_hybrid_ast_view(Document("# Title"), []) == (
            "### Plan AST with Highlighted Failures\n"
            "```text\n"
            '[✓] [000] Heading (Level 1): "Title"\n'
            "```\n"
        )

    def test_degenerate_ast_view_is_bounded(self) -> None:
        # Arrange: an unclosed 10,000-backtick run inside a heading.
        doc = Document("# " + "`" * 10_000)

        # Act
        out = format_hybrid_ast_view(doc, [])

        # Assert: the node preview is capped at 60 characters, so the wrapper
        # fence derived from the AST view stays small and the output is bounded.
        assert "`" * 10_001 not in out
        assert len(out) < 1000
        assert out.startswith("### Plan AST with Highlighted Failures\n")
