from textwrap import dedent

from tests.acceptance.plan_builder import MarkdownPlanBuilder


def test_plan_builder_create_simple_plan():
    """
    Tests that the plan builder can create a basic plan with a title,
    default rationale, and a single action.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Plan Title")
    builder.add_action(
        "READ",
        {
            "Resource": "[docs/test.md](/docs/test.md)",
            "Description": "Read the test file.",
        },
    )

    # Act
    plan_content = builder.build()

    # Assert
    expected_content = dedent(
        """\
        # Test Plan Title
        - **Status:** Green 🟢
        - **Plan Type:** Implementation
        - **Agent:** Developer

        ## Rationale
        ````text
        ### 1. Synthesis
        This is a test plan.

        ### 2. Justification
        This plan is for testing purposes.

        ### 3. Expected Outcome
        The test should pass.

        ### 4. State Dashboard
        [Test Dashboard]
        ````

        ## Action Plan

        ### `READ`
        - **Resource:** [docs/test.md](/docs/test.md)
        - **Description:** Read the test file.
    """
    )
    assert plan_content.strip() == expected_content.strip()
