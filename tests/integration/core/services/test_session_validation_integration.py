import os
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_automated_replan_triggers_on_structure_error(
    monkeypatch, tmp_path, container, mock_llm_client
):
    """
    Scenario: Automated Re-plan triggers on structure error
    """
    os.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "test-structure"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    (turn_01_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Malformed plan (missing Rationale)
    plan_content = """# Bad Structure
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Action Plan

### READ
- Resource: [README.md](/README.md)
- Description: This is fine but the plan is missing Rationale.
"""
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    # Mock structured response
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "# Corrected\nRationale: fixed\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
    mock_response.choices = [mock_choice]
    mock_response.model = "gpt-4o"
    mock_llm_client.get_completion.return_value = mock_response

    result = runner.invoke(app, ["execute", str(plan_path), "-y"])

    assert result.exit_code != 0
    # Use result.output to check both stdout and stderr for diagnostics
    assert "[✗]" in result.output
    assert "Rationale" in result.output
    assert (session_dir / "02" / "plan.md").exists()


def test_manual_mode_validation_failure_no_replan(tmp_path):
    """
    Scenario: Manual mode validation fails correctly.
    It should return a failure report but NOT trigger a re-plan loop.
    """
    os.chdir(tmp_path)
    (tmp_path / "README.md").write_text("content", encoding="utf-8")

    # Plan trying to EDIT a file not in context (no context provided in manual mode)
    plan_content = """# Manual Failure
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
````text
Test Rationale
````

## Action Plan

### `EDIT`
- File Path: [README.md](/README.md)
- Description: Faulty edit.
#### `FIND:`
````text
missing
````
#### `REPLACE:`
````text
new
````
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content, "-y"])

    assert result.exit_code != 0
    assert "Validation Failed" in result.stdout
    assert "The `FIND` block could not be located" in result.stdout
    # Verify no session directories were created
    assert not (tmp_path / ".teddy" / "sessions").exists()


def test_automated_replan_triggers_on_context_error(
    monkeypatch, tmp_path, container, mock_llm_client
):
    """
    Scenario: Context-aware validation failure triggers re-plan.
    """
    os.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "test-context"
    turn_01_dir = session_dir / "01"
    turn_01_dir.mkdir(parents=True)

    (turn_01_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_01_dir / "pathfinder.xml").write_text("<p>S</p>", encoding="utf-8")
    (turn_01_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Plan trying to EDIT a file not in context
    plan_content = """# Context Failure
- Status: Green 🟢
- Plan Type: Implementation
- Agent: Developer

## Rationale
````text
Test Rationale
````

## Action Plan

### `EDIT`
- File Path: [README.md](/README.md)
- Description: Faulty edit.
#### `FIND:`
````text
missing
````
#### `REPLACE:`
````text
new
````
"""
    plan_path = turn_01_dir / "plan.md"
    plan_path.write_text(plan_content, encoding="utf-8")

    # Mock structured response
    from unittest.mock import MagicMock

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "# Corrected\nRationale: fixed\n## Action Plan\n### READ\n- Resource: [README.md](/README.md)\n"
    mock_response.choices = [mock_choice]
    mock_response.model = "gpt-4o"
    mock_llm_client.get_completion.return_value = mock_response

    result = runner.invoke(app, ["execute", str(plan_path), "-y"])

    assert result.exit_code != 0
    assert "Validation Failed" in result.stdout
    assert (session_dir / "02" / "plan.md").exists()
