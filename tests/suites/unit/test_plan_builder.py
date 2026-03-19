from textwrap import dedent
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_builder_supports_all_nine_specialized_methods(container):
    """
    Ensures the builder has specialized methods for all 9 actions.
    This test defines the target API for the refactored builder.
    """
    builder = MarkdownPlanBuilder("Exhaustive Test Plan")

    # Each call should return self to allow chaining
    assert builder.add_create("src/app.py", "print('hello')", overwrite=True) is builder
    builder.add_read("README.md")
    builder.add_edit("src/app.py", "print('hello')", "print('world')", replace_all=True)
    builder.add_execute(
        "pytest",
        expected_outcome="Tests pass",
        allow_failure=True,
        background=False,
        timeout=60,
    )
    builder.add_research(["how to test python"], description="Searching for tests")
    builder.add_prompt("Is this okay?", reference_files=["docs/spec.md"])
    builder.add_invoke(
        "Architect", "Designing system", reference_files=["docs/goals.md"]
    )
    builder.add_return("Feature complete", reference_files=["tests/results.xml"])
    builder.add_prune("old_file.py")

    plan = builder.build()

    # Verify presence of all action types
    assert "### `CREATE`" in plan
    assert "### `READ`" in plan
    assert "### `EDIT`" in plan
    assert "### `EXECUTE`" in plan
    assert "### `RESEARCH`" in plan
    assert "### `PROMPT`" in plan
    assert "### `INVOKE`" in plan
    assert "### `RETURN`" in plan
    assert "### `PRUNE`" in plan


def test_builder_path_normalization(container):
    """Ensures paths are always formatted as root-relative links [path](/path)."""
    builder = MarkdownPlanBuilder("Path Test")
    builder.add_create("docs/architecture/README.md", "content")

    plan = builder.build()
    assert (
        "- **File Path:** [docs/architecture/README.md](/docs/architecture/README.md)"
        in plan
    )


def test_builder_edit_multi_block(container):
    """Ensures add_edit supports multiple find/replace pairs."""
    builder = MarkdownPlanBuilder("Multi-Edit Test")
    # Using a list of tuples for multiple edits
    edits = [("find1", "replace1"), ("find2", "replace2")]
    builder.add_edit("file.txt", edits)

    plan = builder.build()
    assert "#### FIND:\n`````text\nfind1\n`````" in plan
    assert "#### REPLACE:\n`````text\nreplace1\n`````" in plan
    assert "#### FIND:\n`````text\nfind2\n`````" in plan
    assert "#### REPLACE:\n`````text\nreplace2\n`````" in plan


def test_builder_execute_options(container):
    """Verifies that EXECUTE protocol flags are correctly rendered in backticks."""
    builder = MarkdownPlanBuilder("Execute Flags")
    builder.add_execute("exit 1", allow_failure=True, background=True)

    plan = builder.build()
    assert "- **Allow Failure:** `true`" in plan
    assert "- **Background:** `true`" in plan
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


def test_plan_builder_formats_execute_action_from_param():
    """
    Tests that the builder correctly formats an EXECUTE action when the command
    is passed via the `params` dictionary, which is a common pattern in older tests.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Execute Action from Param")
    builder.add_action(
        "EXECUTE",
        params={
            "Description": "Run a test command",
            "command": "echo 'hello from param'",
        },
    )

    # Act
    plan_content = builder.build()

    # Assert
    assert "### `EXECUTE`" in plan_content
    assert "- **Description:** Run a test command" in plan_content
    assert "\n````shell\necho 'hello from param'\n````" in plan_content


def test_plan_builder_formats_execute_action_from_content_block_key():
    """
    Tests that the builder correctly formats an EXECUTE action when the command
    is passed via content_blocks with the key "COMMAND".
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Execute Action from Content Block")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a test command"},
        content_blocks={"COMMAND": ("shell", "echo 'hello from content'")},
    )

    # Act
    plan_content = builder.build()

    # Assert
    assert "### `EXECUTE`" in plan_content
    assert "- **Description:** Run a test command" in plan_content
    assert "\n````shell\necho 'hello from content'\n````" in plan_content


def test_plan_builder_formats_execute_action_correctly():
    """
    Tests that the plan builder correctly formats an EXECUTE action,
    including its command code block. This was identified as a bug source.
    """
    # Arrange
    builder = MarkdownPlanBuilder("Test Execute Action")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a test command"},
        # The key for EXECUTE content_blocks should be empty ""
        content_blocks={"": ("shell", "echo 'hello'")},
    )

    # Act
    plan_content = builder.build()

    # Assert
    assert "### `EXECUTE`" in plan_content
    assert "- **Description:** Run a test command" in plan_content
    assert "\n````shell\necho 'hello'\n````" in plan_content
