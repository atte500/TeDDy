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


def test_parser_handles_thematic_break_between_actions(parser: IPlanParser):
    """Thematic breaks between actions should be ignored (cleaned up)."""
    builder = _b().add_create("f1.txt", "c1").add_create("f2.txt", "c2")
    raw = builder.build()
    # Insert --- before the second CREATE to put the break between the two actions
    plan_content = raw.replace(
        "### `CREATE`\n- **File Path:** [f2.txt](/f2.txt)",
        "---\n### `CREATE`\n- **File Path:** [f2.txt](/f2.txt)",
    )
    plan = parser.parse(plan_content)
    assert len(plan.actions) == 2


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


def test_parser_strips_preamble_text_before_h1(parser: IPlanParser):
    """Preamble text before # heading should be silently stripped."""
    preamble = "Some text before the plan.\n\n"
    raw = preamble + _b().add_read("r.md").build()
    plan = parser.parse(raw)
    # Should parse without errors
    assert plan.title == "Test Plan"
    # Preamble should not appear in raw_content
    assert plan.raw_content is not None
    assert "Some text before the plan" not in plan.raw_content


def test_parser_strips_preamble_with_code_fence(parser: IPlanParser):
    """Preamble containing code fences should be stripped."""
    preamble = "```\ncode in preamble\n```\n\n"
    raw = preamble + _b().add_read("r.md").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"


def test_parser_strips_preamble_with_inline_hash(parser: IPlanParser):
    """Preamble with # inside text (not a heading) should be stripped."""
    preamble = "This has a # symbol but it's not a heading.\n\n"
    raw = preamble + _b().add_read("r.md").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"


def test_parser_handles_no_preamble_correctly(parser: IPlanParser):
    """Plan with no preamble should parse normally."""
    raw = _b().add_read("r.md").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"
    # raw_content should not have any extra prefix
    assert plan.raw_content is not None
    assert plan.raw_content.startswith("# Test Plan")


def test_parser_strips_preamble_with_only_whitespace(parser: IPlanParser):
    """Whitespace-only preamble before H1 should not cause issues."""
    preamble = "   \n\n  "
    raw = preamble + _b().add_read("r.md").build()
    plan = parser.parse(raw)
    assert plan.title == "Test Plan"
