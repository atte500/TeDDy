"""CRLF normalization at plan entry.

Plans pasted from a Windows clipboard carry CRLF line endings. The parser
normalizes them to LF before the Markdown AST is built, so FIND and REPLACE
blocks and message content never carry stray carriage returns.
"""

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

CRLF = "\r\n"


def _crlf_plan(builder: MarkdownPlanBuilder) -> str:
    return builder.build().replace("\n", CRLF)


def test_crlf_plan_edit_blocks_are_normalized_to_lf():
    """EDIT FIND and REPLACE blocks carry LF after a CRLF plan is parsed."""
    builder = MarkdownPlanBuilder("Windows Clipboard Plan").add_edit(
        "sample.txt", "second line", "replacement one\nreplacement two"
    )

    plan = MarkdownPlanParser().parse(_crlf_plan(builder))

    edit = plan.actions[0].params["edits"][0]
    assert edit["find"] == "second line"
    assert edit["replace"] == "replacement one\nreplacement two"
    assert "\r" not in plan.raw_content


def test_crlf_plan_message_content_is_normalized_to_lf():
    """Message content carries LF after a CRLF plan is parsed."""
    builder = MarkdownPlanBuilder("Windows Clipboard Plan").with_message(
        "First paragraph.\n\nSecond paragraph."
    )

    plan = MarkdownPlanParser().parse(_crlf_plan(builder))

    content = plan.actions[0].params["content"]
    assert content == "First paragraph.\n\nSecond paragraph."
    assert "\r" not in content
