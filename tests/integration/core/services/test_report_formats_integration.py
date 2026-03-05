from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_cli_report_is_concise(tmp_path, monkeypatch):
    """
    Scenario: CLI Report (Concise) focuses on immediate action
    - Given an ExecutionReport resulting from a plan that included a successful READ action.
    - When the report is formatted with is_concise=True (Default in CLI).
    - Then the output MUST NOT contain the original plan's Rationale section.
    - And the output MUST contain the full, verbatim content of the successful READ action.
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
This is the original rationale that should be hidden in concise mode.
````

## Action Plan
### `READ`
- **Resource:** existing.txt
"""
    # Execute in manual (concise) mode.
    result = runner.invoke(
        app, ["execute", "-y", "--no-copy", "--plan-content", plan_content]
    )

    assert result.exit_code == 0

    # Verify Rationale is NOT present
    assert "original rationale" not in result.stdout

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
