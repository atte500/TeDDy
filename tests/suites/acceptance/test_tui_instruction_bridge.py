import pytest
from tests.harness.setup.test_environment import TestEnvironment

from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_execution_report_includes_user_request_from_metadata(
    env: TestEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: User adds instructions in TUI.
    Then: The resulting execution report includes a ## User Request section.
    """
    env.setup().with_real_filesystem()
    assert env.workspace, "Workspace must be initialized"
    adapter = CliTestAdapter(monkeypatch, env.workspace)

    # 1. Setup: A plan with user_request in metadata
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Pathfinder
- **Plan Type:** Implementation
- **user_request:** Please refactor the service

## Rationale
````text
### 1. Synthesis
Test.
### 2. Justification
Test.
### 3. Expected Outcome
Test.
### 4. State Dashboard
Test.
````

## Action Plan
### `EXECUTE`
- **Description:** Run test
````shell
echo "hello"
````
"""
    # Create the plan file
    plan_path = env.workspace / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    # 2. Act: Run execute with the plan
    result = adapter.run_cli_command(["execute", "plan.md", "-y", "--no-copy"])

    # 3. Assert: Check for ## User Request section in the report
    assert "## User Request" in result.stdout
    assert "Please refactor the service" in result.stdout


def test_tui_instruction_bridge_capture(env: TestEnvironment):
    """
    Scenario: User uses 'm' binding in TUI.
    This will be implemented in the next turn once the report logic is green.
    """
    pass
