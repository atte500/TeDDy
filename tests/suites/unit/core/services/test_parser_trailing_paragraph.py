"""Parser behavior for paragraphs that trail a completed action plan."""

import pytest

from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def _plan_with_execute() -> str:
    return (
        MarkdownPlanBuilder("Trailing Paragraph Plan")
        .add_execute("git status --short --branch", description="Check status")
        .build()
    )


def test_parser_strips_single_trailing_paragraph():
    parser = MarkdownPlanParser()

    plan = parser.parse(_plan_with_execute() + "\n</br>\n")

    assert len(plan.actions) == 1
    assert plan.raw_content is not None
    assert "git status --short --branch" in plan.raw_content
    assert "</br>" not in plan.raw_content


def test_parser_strips_multiple_trailing_paragraphs():
    parser = MarkdownPlanParser()

    plan = parser.parse(_plan_with_execute() + "\n</br>\n\nEnd of plan.\n")

    assert len(plan.actions) == 1
    assert plan.raw_content is not None
    assert "</br>" not in plan.raw_content
    assert "End of plan." not in plan.raw_content


def test_parser_persists_stripped_plan_to_session_file(tmp_path):
    parser = MarkdownPlanParser()
    turn_directory = tmp_path / ".teddy" / "sessions" / "demo" / "01"
    turn_directory.mkdir(parents=True)
    plan_path = turn_directory / "plan.md"
    raw_plan = _plan_with_execute() + "\n</br>\n"
    plan_path.write_text(raw_plan, encoding="utf-8", newline="")

    plan = parser.parse(raw_plan, plan_path=str(plan_path))

    persisted = plan_path.read_text(encoding="utf-8")
    assert "</br>" not in persisted
    assert persisted == plan.raw_content


def test_parser_rejects_paragraph_between_actions():
    content = (
        _plan_with_execute()
        + "\nThis text sits between action blocks.\n\n"
        + "### `READ`\n- **Resource:** notes.md\n"
    )

    with pytest.raises(InvalidPlanError, match="a Level 3 Action Heading"):
        MarkdownPlanParser().parse(content)


def test_parser_rejects_trailing_paragraph_followed_by_stray_fence():
    content = _plan_with_execute() + "\n</br>\n\n```\nstray block\n```\n"

    with pytest.raises(InvalidPlanError, match="a Level 3 Action Heading"):
        MarkdownPlanParser().parse(content)


def test_parser_rejects_improperly_nested_code_fences():
    content = (
        MarkdownPlanBuilder("Improper Nesting").build()
        + "\n### `CREATE`\n- **File Path:** improper.py\n"
        + "- **Description:** Improper nesting example\n"
        + "```\n```\nthis code block is not properly nested\n```\n"
        + "the structure is broken here\nso validation must still fail\n```\n"
    )

    with pytest.raises(InvalidPlanError, match="a Level 3 Action Heading"):
        MarkdownPlanParser().parse(content)


def test_parser_rejects_trailing_paragraph_when_no_action_was_parsed():
    content = MarkdownPlanBuilder("Empty Action Plan").build() + "\n</br>\n"

    with pytest.raises(InvalidPlanError):
        MarkdownPlanParser().parse(content)
