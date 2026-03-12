from unittest.mock import MagicMock
from typer.testing import CliRunner
from teddy_executor.__main__ import app
from teddy_executor.core.ports.outbound.llm_client import ILlmClient

runner = CliRunner()


def test_teddy_start_triggers_planning(tmp_path, monkeypatch, container):
    """
    Scenario: teddy start triggers planning immediately
    Given I want to start a new session.
    When I run teddy start "my-feature".
    And I provide "Initial instructions" at the prompt.
    Then a session "my-feature" MUST be created.
    And a plan.md MUST be generated in turn 01/.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()  # Simulate project root

    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")

    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text("<prompt>PF</prompt>", encoding="utf-8")

    # Mock LLM
    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = """# Plan: Streamlined Init
- Status: Green
- Plan Type: feat
- Agent: Dev

## Rationale
``````
OK
``````

## Action Plan
### `EXECUTE`
- Description: dummy
````shell
echo 'dummy'
````
"""
    container.register(ILlmClient, instance=mock_llm)

    # Act
    # We simulate user input for the prompt that 'start' should now trigger
    result = runner.invoke(
        app, ["start", "my-feature"], input="Initial instructions\ny\n"
    )

    # Assert
    assert result.exit_code == 0
    plan_file = tmp_path / ".teddy" / "sessions" / "my-feature" / "01" / "plan.md"
    assert plan_file.exists()
    assert (
        "Initial instructions"
        in mock_llm.get_completion.call_args[1]["messages"][1]["content"]
    )
