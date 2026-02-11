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
        **Vertical Slice:** `docs/slices/test.md`
        **Development Workflow:**
        - [ ] Phase 1
        **Active Phase Details:**
        *   **Test**
        **Architectural Notes:**
        - None
        ````

        ## Action Plan

        ### `READ`
        - **Resource:** [docs/test.md](/docs/test.md)
        - **Description:** Read the test file.
    """
    )
    assert plan_content.strip() == expected_content.strip()


def test_plan_builder_create_plan_with_edit_action():
    """
    Tests that the plan builder can correctly format an EDIT action
    with FIND and REPLACE blocks.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Edit Action")
    builder.add_action(
        "EDIT",
        params={
            "File Path": "test.txt",
            "Description": "A test edit.",
        },
        content_blocks={
            "FIND:": ("text", "old content"),
            "REPLACE:": ("text", "new content"),
        },
    )

    # Act
    plan_content = builder.build()

    # Assert
    expected_content = dedent(
        """\
        # Test Edit Action
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
        **Vertical Slice:** `docs/slices/test.md`
        **Development Workflow:**
        - [ ] Phase 1
        **Active Phase Details:**
        *   **Test**
        **Architectural Notes:**
        - None
        ````

        ## Action Plan

        ### `EDIT`
        - **File Path:** test.txt
        - **Description:** A test edit.

        #### FIND:
        `````text
        old content
        `````
        #### REPLACE:
        `````text
        new content
        `````
    """
    )
    assert plan_content.strip() == expected_content.strip()
