import pytest
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    """Fixture providing a CliTestAdapter anchored to a temporary workspace."""
    # Setup the environment (handles DI patching)
    TestEnvironment(monkeypatch, workspace=tmp_path).setup()
    # Return the adapter initialized with the raw monkeypatch fixture
    return CliTestAdapter(monkeypatch, cwd=tmp_path)


def test_structural_validation_error_format(adapter):
    """
    Scenario 1: Structural Validation Error
    Given a plan with top-level structural errors (missing ## Rationale)
    When the plan is executed
    Then it should fail with a rich diagnostic report.
    """
    # Note: We use a raw string here because MarkdownPlanBuilder enforces a valid structure.
    # Testing structural failure requires breaking that protocol.
    plan_content = """# Plan Missing Rationale
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
"""
    result = adapter.run_execute_with_plan(plan_content)

    assert result.exit_code != 0
    output = result.stdout

    # Assertions for the rich format
    assert '[✓] [000] Heading (Level 1): "Plan Missing Rationale"' in output
    assert '[✓] [001] List: "Status: Green 🟢' in output
    assert (
        "[✗] [002] Heading (Level 2): \"Action Plan\" (Error: Expected a Level 2 Heading containing 'Rationale')"
        in output
    )
    assert "### Actual Document Structure" in output


def test_logical_validation_error_format(adapter, tmp_path):
    """
    Scenario 2: Logical Validation Error (Missing File)
    Given an EDIT action on a non-existent file
    Then the action heading itself must be marked [✗].
    """
    plan_content = (
        MarkdownPlanBuilder("Plan with Missing File")
        .add_edit(
            path="non_existent_file.py",
            find_replace="print('Hello')",
            replace="print('Goodbye')",
            description="Missing file",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "File to edit does not exist: non_existent_file.py" in output
    assert (
        '[✗] [005] Heading (Level 3): "EDIT" (Error: File to edit does not exist: non_existent_file.py)'
        in output
    )
    assert '  [✓] [006] List: "File Path: non_existent_file.py' in output


def test_surgical_code_block_highlighting(adapter, tmp_path):
    """
    Scenario 3: Surgical Code Block Highlighting
    Given an EDIT action on an existing file but with a non-matching FIND block
    Then the action heading must be [✓]
    And the specific FIND Code Block must be [✗].
    """
    (tmp_path / "README.md").write_text("# Test README", encoding="utf-8")

    plan_content = (
        MarkdownPlanBuilder("Plan with Mismatched Find")
        .add_edit(
            path="README.md",
            find_replace="THIS CONTENT DEFINITELY DOES NOT EXIST IN README",
            replace="NEW CONTENT",
            description="Matching file, non-matching content",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "The `FIND` block could not be located" in output
    assert "### Plan AST with Highlighted Failures" in output
    assert '[✓] [005] Heading (Level 3): "EDIT"' in output
    assert '  [✓] [006] List: "File Path: README.md' in output
    # Relaxed assertion to be resilient to the specific number of backticks used in the fence
    assert "[✗] [008] Code Block" in output
    assert '"THIS CONTENT DEFINITELY DOES NOT EXIST IN README"' in output
    assert (
        "(Error: The `FIND` block could not be located in the file: README.md)"
        in output
    )
    assert '  [✓] [009] Heading (Level 4): "REPLACE:"' in output
    assert "Code Block" in output
    assert '"NEW CONTENT"' in output
