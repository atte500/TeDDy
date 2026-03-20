from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_structural_validation_error_format(tmp_path, monkeypatch):
    """Scenario: Plan with top-level structural errors fails with rich diagnostic AST report."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    # TEDDY_DEBUG enables AST visualization in the output
    monkeypatch.setenv("TEDDY_DEBUG", "true")
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "README.md").touch()

    # Manually construct a broken plan (missing Rationale)
    plan = """# Plan Missing Rationale
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
"""

    result = adapter.run_execute_with_plan(plan, tmp_path)

    assert result.exit_code != 0
    output = result.stdout

    # Assertions for the rich AST format
    assert "[✓]" in output and 'Heading (Level 1): "Plan Missing Rationale"' in output
    assert "[✓]" in output and 'List: "Status: Green 🟢' in output
    assert "[✗]" in output and 'Heading (Level 2): "Action Plan"' in output
    assert "Error: Expected a Level 2 Heading containing 'Rationale'" in output
    assert "### Actual Response Structure" in output


def test_logical_validation_error_format(tmp_path, monkeypatch):
    """Scenario: EDIT action on a non-existent file marks the action heading as [✗]."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    monkeypatch.setenv("TEDDY_DEBUG", "true")
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Plan with Missing File")
        .add_edit(
            "non_existent_file.py",
            "print('Hello')",
            "print('Goodbye')",
            description="Missing file",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path)
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "File to edit does not exist: non_existent_file.py" in output
    assert "[✗]" in output and 'Heading (Level 3): "EDIT"' in output
    assert "Error: File to edit does not exist: non_existent_file.py" in output


def test_surgical_code_block_highlighting(tmp_path, monkeypatch):
    """Scenario: EDIT action on existing file with non-matching FIND block highlights the specific block as [✗]."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    monkeypatch.setenv("TEDDY_DEBUG", "true")
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "README.md").write_text("# Test README", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Plan with Mismatched Find")
        .add_edit(
            "README.md",
            "THIS CONTENT DEFINITELY DOES NOT EXIST IN README",
            "NEW CONTENT",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path)
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "The `FIND` block could not be located" in output

    # AST Visualization
    assert "### Plan AST with Highlighted Failures" in output
    assert "[✓]" in output and "EDIT" in output
    assert (
        "[✗]" in output and "THIS CONTENT DEFINITELY DOES NOT EXIST IN README" in output
    )
    assert (
        "(Error: The `FIND` block could not be located in the file: README.md)"
        in output
    )
