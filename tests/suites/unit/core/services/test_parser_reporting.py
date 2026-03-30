from mistletoe import Document
from teddy_executor.core.services.parser_reporting import format_node_name


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
