from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser

from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_parser_ignores_trailing_indented_whitespace():
    """
    Reproduces the bug where trailing 4-space indentation is
    misinterpreted as an unexpected code block.
    """
    parser = MarkdownPlanParser()
    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_create("test.txt", "content")

    # Build a valid plan and append 4 spaces
    plan_with_trailing_indent = builder.build() + "\n    "

    # This should succeed, but currently it likely raises a validation error
    # about an unexpected code block because mistletoe sees an indented code block.
    plan = parser.parse(plan_with_trailing_indent)
    assert len(plan.actions) == 1


def test_parser_ignores_trailing_tabs():
    """
    Ensures trailing tabs are also ignored.
    """
    parser = MarkdownPlanParser()
    builder = MarkdownPlanBuilder("Test Plan")
    builder.add_read("test.txt")
    plan_with_trailing_tabs = builder.build() + "\n\t\t"

    # Expectation: Success
    parser.parse(plan_with_trailing_tabs)
