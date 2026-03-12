import textwrap
import pytest
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import MISMATCH_INDICATOR


def test_parser_highlights_multiple_structural_mismatches():
    """
    Scenario: Multi-Highlight AST Mismatches
    Given a plan with multiple structural errors (missing metadata list AND wrong heading level)
    When the plan is parsed
    Then the error message should highlight all offending nodes.
    """
    parser = MarkdownPlanParser()

    # A plan missing the Metadata List (Node 1) and having a wrong heading level for Rationale (Node 2)
    # Correct order: H1, List, H2 (Rationale), Code, H2 (Action Plan)
    malformed_plan = textwrap.dedent("""\
        # A Malformed Plan
        This is a paragraph instead of a list.
        ### Wrong Heading Level (Rationale)
        ```text
        Some rationale
        ```
        ## Action Plan
    """)

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(malformed_plan)

    error_msg = str(excinfo.value)

    # Ensure the AST summary is present
    assert "--- Actual Document Structure ---" in error_msg

    # We expect highlights on the paragraph (Node 1) and the H3 heading (Node 2)
    # The current implementation will only highlight one of them (likely the first one it hits)
    # Note: Indices are 0-based.
    # [000] Heading (Level 1)
    # [001] Paragraph (Mismatch: expected List)
    # [002] Heading (Level 3) (Mismatch: expected H2 Rationale)

    # We assert that the indicator appears at least twice in the structure section
    structure_section = error_msg.split("--- Actual Document Structure ---")[-1]
    indicator_count = structure_section.count(MISMATCH_INDICATOR)

    expected_min_indicators = 2
    assert indicator_count >= expected_min_indicators, (
        f"Expected at least {expected_min_indicators} mismatch indicators, "
        f"found {indicator_count} in:\n{structure_section}"
    )
    assert "[001] Paragraph" in structure_section
    assert (
        f'Paragraph: "This is a paragraph instead of a list."{MISMATCH_INDICATOR}'
        in structure_section
    )
    assert (
        f'Heading (Level 3): "Wrong Heading Level (Rationale)"{MISMATCH_INDICATOR}'
        in structure_section
    )


def test_parser_highlights_multiple_mismatches_in_action_plan():
    """
    Scenario: Multi-Highlight AST Mismatches (Action Plan)
    Given a plan with multiple structural errors inside the Action Plan section
    When the plan is parsed
    Then the error message should highlight all offending nodes in the Action Plan.
    """
    parser = MarkdownPlanParser()

    malformed_plan = textwrap.dedent("""\
        # Valid Title
        - Status: Green
        - Agent: Pathfinder

        ## Rationale
        ```text
        Valid rationale
        ```

        ## Action Plan
        ### `EXECUTE`
        - Description: Valid
        ```shell
        ls
        ```
        This is an invalid paragraph.
        ### `CREATE`
        - File Path: /tmp/test
        - Description: Valid
        ```text
        content
        ```
        This is another invalid paragraph.
    """)

    with pytest.raises(InvalidPlanError) as excinfo:
        parser.parse(malformed_plan)

    error_msg = str(excinfo.value)
    structure_section = error_msg.split("--- Actual Document Structure ---")[-1]

    # We expect highlights on both invalid paragraphs
    assert (
        f'Paragraph: "This is an invalid paragraph."{MISMATCH_INDICATOR}'
        in structure_section
    )

    # Add a very long paragraph to test truncation at 60 chars
    long_msg = "This is a very long paragraph that exceeds the sixty character limit to test truncation."
    truncated_msg = long_msg[:60].strip() + "..."

    malformed_plan_long = textwrap.dedent(f"""\
        # Valid Title
        - Status: Green
        - Agent: Pathfinder

        ## Rationale
        ```text
        Valid rationale
        ```

        ## Action Plan
        {long_msg}
    """)

    with pytest.raises(InvalidPlanError) as excinfo_long:
        parser.parse(malformed_plan_long)

    structure_long = str(excinfo_long.value).split("--- Actual Document Structure ---")[
        -1
    ]
    assert f'Paragraph: "{truncated_msg}"{MISMATCH_INDICATOR}' in structure_long

    expected_min_indicators = 2
    indicator_count = structure_section.count(MISMATCH_INDICATOR)
    assert indicator_count >= expected_min_indicators
    expected_min_indicators = 2
    assert indicator_count >= expected_min_indicators
