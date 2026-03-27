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


def test_tui_instruction_bridge_m_binding_captures_message(
    env: TestEnvironment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Scenario: User reviews a plan in Console (Bridge Parity) and adds a message via 'm'.
    Then: The message is captured and appears in the final execution report.
    """
    env.setup().with_real_filesystem().with_real_system_environment().with_real_shell().with_real_interactor()
    assert env.workspace, "Workspace must be initialized"

    # We use a standard plan that should trigger the TUI
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Pathfinder
- **Plan Type:** Implementation

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
    plan_path = env.workspace / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    adapter = CliTestAdapter(monkeypatch, env.workspace)

    # We need a way to mock the editor output.
    # This deliverable focuses on ADDING this capability to the adapter.
    # For now, we call a method we EXPECT to exist.
    adapter.set_mock_editor_output(
        "Refactor this service specifically for performance."
    )

    # Run execute in interactive mode (no -y)
    # We simulate pressing 'm' (to add message), then 'y' (to approve)
    # We force --console mode because CliRunner cannot drive Textual TUI apps.
    result = adapter.run_cli_command(
        ["execute", "plan.md", "--no-copy", "--console"], input="m\ny\n"
    )
    # Assert: Check for ## User Request section in the report
    assert "## User Request" in result.stdout
    assert "Refactor this service specifically for performance." in result.stdout
