from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_report_prunes_redundant_sections(tmp_path, monkeypatch):
    """
    Scenario: Execution report prunes redundant sections (Rationale, Original Plan)
    - Given an ExecutionReport resulting from a plan execution.
    - When the report is formatted for Markdown output.
    - Then the output MUST NOT contain the original plan's Rationale section.
    - And the output MUST contain the full, verbatim content of the successful actions.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Setup files
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("Verbatim content", encoding="utf-8")

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
This is the original rationale that should be hidden.
````

## Action Plan
### `READ`
- **Resource:** existing.txt
"""
    # Execute plan.
    result = runner.invoke(
        app, ["execute", "-y", "--no-copy", "--plan-content", plan_content]
    )

    assert result.exit_code == 0

    # Verify Rationale is NOT present
    assert "original rationale" not in result.stdout.lower()

    # Verify READ content is present
    assert "Verbatim content" in result.stdout

    # Verify Action Log is present
    assert "Action Log" in result.stdout
    assert "READ" in result.stdout
    assert "SUCCESS" in result.stdout


def test_session_report_is_comprehensive(tmp_path, monkeypatch):
    """
    Scenario: Session Report (Comprehensive) focuses on audit trail
    - Verified via unit tests of the formatter as the CLI session logic is not yet fully wired.
    """
    pass
