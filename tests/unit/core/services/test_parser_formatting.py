import mistletoe
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.parser_infrastructure import MISMATCH_INDICATOR


def test_format_structural_mismatch_msg_highlights_multiple_nodes():
    parser = MarkdownPlanParser()
    doc = mistletoe.Document("# Title\nPara\n## Rationale")
    children = list(doc.children)

    # Simulate multiple offending nodes (e.g., Node 1 and Node 2)
    offending_nodes = [children[1], children[2]]

    # We need to test the internal _format_structural_mismatch_msg or
    # the AST summary logic inside parse().
    # The requirement specifically mentions _format_structural_mismatch_msg in the deliverables.

    # Note: _format_structural_mismatch_msg currently only accepts one 'actual_node'.
    # I will first verify it fails to highlight multiple if I try to pass them.

    msg = parser._format_structural_mismatch_msg(
        doc, expected="something", mismatch_idx=-1, actual_node=offending_nodes
    )

    indicator_count = msg.count(MISMATCH_INDICATOR)
    expected_min_indicators = 2
    assert indicator_count >= expected_min_indicators, (
        f"Expected multiple highlights, got {indicator_count}"
    )
