import mistletoe
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser


def test_format_structural_mismatch_msg_highlights_multiple_nodes():
    parser = MarkdownPlanParser()
    doc = mistletoe.Document("# Title\nPara\n## Rationale")
    children = list(doc.children)

    # Simulate multiple offending nodes (e.g., Node 1 and Node 2)
    # The new implementation uses a list of offending nodes and prefixes them with [✗]
    offending_nodes = [children[1], children[2]]

    msg = parser._format_structural_mismatch_msg(
        doc, expected="something", mismatch_idx=1, actual_node=offending_nodes
    )

    # We expect [✗] for Node 1 and Node 2
    expected_failures = 2
    assert "[✓] [000] Heading (Level 1)" in msg
    assert "[✗] [001] Paragraph" in msg
    assert "[✗] [002] Heading (Level 2)" in msg
    assert "(Error: something)" in msg
    assert msg.count("[✗]") == expected_failures
