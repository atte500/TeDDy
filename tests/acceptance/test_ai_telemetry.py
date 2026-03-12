import yaml
import textwrap
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from typer.testing import CliRunner
from teddy_executor.__main__ import app
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor

runner = CliRunner()


@pytest.fixture
def mock_interactor(container):
    mock = MagicMock(spec=IUserInteractor)
    # Default behavior: approve everything
    mock.confirm_action.return_value = (True, "")
    mock.confirm_manual_handoff.return_value = (True, "")
    # Default response for planning prompt
    mock.ask_question.return_value = "do it"

    # Side effect to ensure messages are captured by CliRunner
    import typer

    def echo_message(msg):
        typer.echo(msg)

    mock.display_message.side_effect = echo_message
    mock.notify_skipped_action.side_effect = lambda action, reason: echo_message(
        f"[SKIPPED] {action.type}: {reason}"
    )

    container.register(IUserInteractor, instance=mock)
    return mock


def make_mock_response(content, model="gpt-4o"):
    mock_response = MagicMock()
    mock_response.model = model
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def test_ai_telemetry_and_logging(
    tmp_path, monkeypatch, mock_llm_client, mock_interactor
):
    """
    Scenario: AI Transparency & Telemetry
    Verifies that input.log is created, prompts use agent names, and telemetry is displayed.
    """
    monkeypatch.chdir(tmp_path)

    # Fix Environment
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")

    # Mock LLM response for planning
    valid_plan = textwrap.dedent("""\
        # Plan: New Feature
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Pathfinder

        ## Rationale
        ``````
        Rationale content.
        ``````

        ## Action Plan
        ### `CREATE`
        - **File Path:** file.txt
        - **Description:** test
        ``````
        content
        ``````
        """)
    mock_llm_client.get_completion.return_value = make_mock_response(valid_plan)
    mock_llm_client.get_token_count.return_value = 15200
    mock_llm_client.get_completion_cost.return_value = 0.04

    # Run 'start' - interactor mock will handle inputs
    result = runner.invoke(app, ["start", "--agent", "pathfinder"])
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    session_dir = Path(".teddy/sessions/new-feature")
    turn_dir = session_dir / "01"

    # 2. Verify input.log exists and contains payload
    input_log = turn_dir / "input.log"
    assert input_log.exists(), "input.log should be created in the turn directory"
    log_content = input_log.read_text()
    assert "role" in log_content
    assert "content" in log_content
    assert "pathfinder" in log_content.lower()

    # 3. Verify agent prompt is saved with its name
    assert (turn_dir / "pathfinder.xml").exists(), (
        "Agent prompt should be saved as pathfinder.xml"
    )

    # 4. Verify telemetry in CLI output
    assert "Model: gpt-4o" in result.output
    assert "Context: 15.2k tokens" in result.output
    assert "Session Cost: $0.0400" in result.output


def test_telemetry_persistence_across_turns(
    tmp_path, monkeypatch, mock_llm_client, mock_interactor
):
    """
    Verifies that cumulative cost is persisted and updated across turns.
    """
    monkeypatch.chdir(tmp_path)

    # Fix Environment
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")

    # Turn 1
    plan_1 = textwrap.dedent("""\
        # Plan: Turn 1
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Pathfinder

        ## Rationale
        ``````
        test 1
        ``````

        ## Action Plan
        ### `EXECUTE`
        - **Description:** test 1
        ````shell
        echo 1
        ````
        """)
    mock_llm_client.get_completion.return_value = make_mock_response(plan_1)
    mock_llm_client.get_completion_cost.return_value = 0.01
    mock_llm_client.get_token_count.return_value = 100

    runner.invoke(app, ["start", "turn-1", "--agent", "pathfinder"])

    session_dir = Path(".teddy/sessions/turn-1")
    meta_1_path = session_dir / "01" / "meta.yaml"
    meta_1 = yaml.safe_load(meta_1_path.read_text())
    assert meta_1["cumulative_cost"] == 0.0
    assert meta_1["turn_cost"] == 0.01  # noqa: PLR2004

    # Turn 2 (via resume)
    plan_2 = textwrap.dedent("""\
        # Plan: Turn 2
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Pathfinder

        ## Rationale
        ``````
        test 2
        ``````

        ## Action Plan
        ### `EXECUTE`
        - **Description:** test 2
        ````shell
        echo 2
        ````
        """)
    mock_llm_client.get_completion.return_value = make_mock_response(plan_2)
    mock_llm_client.get_completion_cost.return_value = 0.02

    result = runner.invoke(app, ["resume", str(session_dir)])
    assert result.exit_code == 0, f"CLI failed: {result.output}"

    meta_2_path = session_dir / "02" / "meta.yaml"
    meta_2 = yaml.safe_load(meta_2_path.read_text())
    assert meta_2["cumulative_cost"] == 0.01  # noqa: PLR2004
    assert meta_2["turn_cost"] == 0.02  # noqa: PLR2004

    # Verify that the cost in Turn 2 is displayed and includes previous turns
    assert "Session Cost: $0.0300" in result.output


def test_input_log_during_replan(
    tmp_path, monkeypatch, mock_llm_client, mock_interactor
):
    """
    Verifies that input.log is created even during automated re-planning.
    """
    monkeypatch.chdir(tmp_path)

    # Fix Environment
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")

    # 1. Start session with a plan that will fail validation
    bad_plan = textwrap.dedent("""\
        # Plan: Bad Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Pathfinder

        ## Rationale
        ``````
        bad
        ``````

        ## Action Plan
        ### `EDIT`
        - **File Path:** non_existent.py
        - **Description:** fail
        #### `FIND:`
        ``````
        content
        ``````
        #### `REPLACE:`
        ``````
        new
        ``````
        """)
    corrected_plan = textwrap.dedent("""\
        # Plan: Corrected Plan
        - Status: Green 🟢
        - Plan Type: Implementation
        - Agent: Pathfinder

        ## Rationale
        ``````
        ok
        ``````

        ## Action Plan
        ### `CREATE`
        - **File Path:** ok.txt
        - **Description:** ok
        ``````
        ok
        ``````
        """)
    mock_llm_client.get_completion.side_effect = [
        make_mock_response(bad_plan),
        make_mock_response(corrected_plan),
    ]
    mock_llm_client.get_token_count.return_value = 100
    mock_llm_client.get_completion_cost.return_value = 0.01

    result = runner.invoke(app, ["start", "replan-test"])
    # Validation failure correctly returns exit code 1 even if re-plan triggered
    assert result.exit_code == 1, (
        f"CLI should return 1 on validation failure: {result.output}"
    )

    session_dir = Path(".teddy/sessions/replan-test")
    if not session_dir.exists():
        session_dir = Path(".teddy/sessions/bad-plan")

    input_log_02 = session_dir / "02" / "input.log"
    assert input_log_02.exists()
    assert "Validation Errors" in input_log_02.read_text()
