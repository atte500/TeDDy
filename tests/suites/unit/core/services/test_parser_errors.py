import pytest
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def parser(container) -> IPlanParser:
    return container.resolve(IPlanParser)


def _b():
    return MarkdownPlanBuilder("Test Plan")


def test_parser_raises_error_on_unknown_action(parser: IPlanParser):
    """Verify error on unknown action header."""
    plan_content = _b().build() + "\n### `UNKNOWN_ACTION`\n- **Description:** Fail\n"
    with pytest.raises(InvalidPlanError, match="Unknown action type: UNKNOWN_ACTION"):
        parser.parse(plan_content)


def test_parser_raises_error_on_thematic_break_between_actions(parser: IPlanParser):
    """Verify error on thematic break (---) between actions."""
    plan_content = (
        _b()
        .add_create("f1.txt", "c1")
        .build()
        .replace("\n### `CREATE`", "---\n### `CREATE`", 1)  # Insert break
    )
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)
    assert "ThematicBreak (Error: Expected a Level 3 Action Heading)" in str(
        excinfo.value
    )


def test_parser_raises_error_on_malformed_structure_between_actions(
    parser: IPlanParser,
):
    """Verify error on free text between action blocks."""
    bad_text = "This is some free text that shouldn't be here."
    # Use a simple READ action to avoid having to append a mandatory code block
    plan_content = (
        _b().add_execute("echo 1").build()
        + f"\n{bad_text}\n\n### `READ`\n- **Resource:** r.md\n"
    )
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)
    assert f'Paragraph: "{bad_text}" (Error: Expected a Level 3 Action Heading)' in str(
        excinfo.value
    )


def test_parser_rejects_improperly_nested_code_fences(parser: IPlanParser):
    """Verify rejection of improperly nested code blocks."""
    # Outer ``` but inner also ```
    plan_content = (
        _b().build()
        + "\n### `CREATE`\n- **File Path:** f.md\n```markdown\n```shell\necho 1\n```\n```\n"
    )
    with pytest.raises(InvalidPlanError, match="a Level 3 Action Heading"):
        parser.parse(plan_content)


def test_parser_rejects_user_provided_invalidly_nested_edit_plan(parser: IPlanParser):
    """Real-world example: inner fence (````shell) same as outer (````python)."""
    inner = "````shell\ncd src\n````"
    plan_content = _b().add_edit("t.py", "FIND", f"REPLACE\n{inner}").build()
    # Force a mismatch by lowering both outer fences to match the inner (4 backticks)
    plan_content = plan_content.replace("`````", "````")

    with pytest.raises(InvalidPlanError, match="a Level 3 Action Heading"):
        parser.parse(plan_content)


def test_parser_raises_error_if_no_title_found(parser: IPlanParser):
    """Verify error with no H1 heading."""
    with pytest.raises(InvalidPlanError, match="Expected a Level 1 Heading"):
        parser.parse("## Just a Sub-heading\n- Item")


def test_parser_raises_error_with_indicator_on_missing_replace_block(
    parser: IPlanParser,
):
    """Verify error when EDIT is missing a REPLACE block."""
    plan_content = (
        _b().build()
        + "\n### `EDIT`\n- **File Path:** d.txt\n#### `FIND:`\n````\nf\n````\nParagraph\n"
    )
    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(plan_content)
    assert "Missing REPLACE block after FIND block" in str(excinfo.value)
    assert 'Paragraph: "Paragraph"' in str(excinfo.value)


def test_parser_raises_error_with_indicator_on_structural_mismatch(parser: IPlanParser):
    """Verify error when top-level structure is invalid (missing Rationale)."""
    plan_content = "# Title\n- **Status:** G\n- **Agent:** D\n\n## Action Plan\n### `READ`\n- Resource: R.md\n"
    with pytest.raises(InvalidPlanError, match="Plan structure is invalid") as excinfo:
        parser.parse(plan_content)
    assert '[✗] [002] Heading (Level 2): "Action Plan"' in str(excinfo.value)
