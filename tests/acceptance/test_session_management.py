from unittest.mock import MagicMock

import yaml
from typer.testing import CliRunner

from teddy_executor.__main__ import app
from teddy_executor.core.ports.outbound.llm_client import ILlmClient

runner = CliRunner()


def make_mock_response(content, model="gpt-4o"):
    mock_response = MagicMock()
    mock_response.model = model
    mock_message = MagicMock()
    mock_message.content = content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    return mock_response


def test_teddy_start_bootstraps_session(tmp_path, monkeypatch, container):
    """
    Scenario: teddy start bootstraps a session
    Given no existing session named "feat-x".
    When I run teddy start feat-x.
    Then a directory .teddy/sessions/feat-x/01/ MUST be created.
    And .teddy/sessions/feat-x/session.context MUST exist and contain the content of .teddy/init.context.
    And 01/pathfinder.xml MUST be populated with the default agent prompt.
    And 01/meta.yaml MUST contain a valid turn_id and creation_timestamp.
    """
    # Arrange
    # Change CWD to tmp_path to isolate filesystem side effects
    monkeypatch.chdir(tmp_path)

    # Pre-seed init.context as per specification
    init_context_content = "README.md\ndocs/project/PROJECT.md"
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text(init_context_content, encoding="utf-8")

    # Seed default prompt and .git to simulate project root
    (tmp_path / ".git").mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder prompt</prompt>", encoding="utf-8"
    )

    # Mock LLM
    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response("""# Plan: Streamlined Init
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
""")
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    # Act
    result = runner.invoke(app, ["start", "feat-x"], input="initial instructions\ny\n")

    # Assert
    assert result.exit_code == 0

    session_dir = teddy_dir / "sessions" / "feat-x"
    turn_dir = session_dir / "01"

    assert turn_dir.is_dir()

    # Check session.context
    session_context = session_dir / "session.context"
    assert session_context.exists()
    assert session_context.read_text(encoding="utf-8").strip() == init_context_content

    # Check pathfinder.xml
    # Note: We assume 'pathfinder' is the default agent as per spec
    system_prompt = turn_dir / "pathfinder.xml"
    assert system_prompt.exists()
    assert "Pathfinder" in system_prompt.read_text(encoding="utf-8")

    # Check meta.yaml
    meta_file = turn_dir / "meta.yaml"
    assert meta_file.exists()
    with open(meta_file, "r", encoding="utf-8") as f:
        meta_data = yaml.safe_load(f)
        assert "turn_id" in meta_data
        assert "creation_timestamp" in meta_data
        assert meta_data["turn_id"] == "01"


def test_teddy_plan_injects_turn_1_hint(tmp_path, monkeypatch, container):
    """
    Scenario: teddy plan injects Turn 1 alignment hint
    Given a session directory for turn 01.
    When I run teddy plan -m "Do stuff".
    Then the user message sent to the LLM MUST contain the Turn 1 alignment hint.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "hint-test"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text("system prompt", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response("# Plan")
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    # Act
    monkeypatch.chdir(turn_dir)
    runner.invoke(app, ["plan", "-m", "Do stuff"])

    # Assert
    args, kwargs = mock_llm.get_completion.call_args
    sent_message = kwargs["messages"][1]["content"]
    assert "Do stuff" in sent_message
    assert "aligned" in sent_message.lower()
    assert "intentions" in sent_message.lower()


def test_teddy_resume_executes_pending_plan(tmp_path, monkeypatch):
    """
    Scenario: teddy resume executes pending plan
    Given a turn directory with plan.md but no report.md.
    When I run teddy resume.
    Then it MUST behave like teddy execute.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "resume-test"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    # Setup state for execution
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text("prompt", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    plan_content = """# Plan
- Status: Green 🟢
- Plan Type: Testing
- Agent: Developer

## Rationale
```
Rationale content.
```

## Action Plan
### `EXECUTE`
- **Description:** test
````shell
echo hello
````
"""
    (turn_dir / "plan.md").write_text(plan_content, encoding="utf-8")

    # Act
    monkeypatch.chdir(turn_dir)
    result = runner.invoke(app, ["resume", "-y", "--no-copy"])

    # Assert
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert (turn_dir / "report.md").exists()
    assert (session_dir / "02").exists()  # Verify transition happened


def test_teddy_resume_prompts_for_new_plan(monkeypatch, tmp_path, container):
    """
    Scenario: teddy resume prompts for new plan when turn is empty.
    """
    # Setup
    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "02"
    turn_dir.mkdir(parents=True)
    (session_dir / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").write_text("<prompt/>")
    (turn_dir / "meta.yaml").write_text("turn_id: '02'\nparent_turn_id: '01'")

    # Mock LLM to return a valid plan
    from teddy_executor.core.ports.outbound.llm_client import ILlmClient

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response("""# Plan: Resume Plan
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
""")
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01

    container.register(ILlmClient, instance=mock_llm)

    # Act
    monkeypatch.chdir(turn_dir)
    # We provide the user message via input to satisfy typer.prompt
    result = runner.invoke(app, ["resume"], input="My New Feature\n")

    # Assert
    assert result.exit_code == 0
    assert (turn_dir / "plan.md").exists()
    assert "# Plan" in (turn_dir / "plan.md").read_text()

    # Verify hint was injected
    expected_message = "My New Feature\n\n*(Stop to reply to this user request and ensure alignment before proceeding)*"
    mock_llm.get_completion.assert_called_once()
    args, kwargs = mock_llm.get_completion.call_args
    assert expected_message in kwargs["messages"][1]["content"]


def test_teddy_start_dynamic_renaming_and_flow(tmp_path, monkeypatch, container):
    """
    Scenario: Rename 'new' to 'start' and enable dynamic naming
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")

    prompts_dir = teddy_dir / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text(
        "<prompt>test</prompt>", encoding="utf-8"
    )

    # Mock LLM to return a plan with a specific H1
    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response("""# Plan: Initialize User Auth
- Status: Green
- Plan Type: feat
- Agent: Dev

## Rationale
``````
Testing dynamic rename.
``````

## Action Plan
### `EXECUTE`
- Description: test
````shell
echo 'hello from dynamic session'
````""")
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    # Act
    result = runner.invoke(
        app, ["start"], input="My prompt\ny\n", catch_exceptions=False
    )

    # Assert
    assert result.exit_code == 0
    sessions_root = teddy_dir / "sessions"
    assert sessions_root.is_dir()
    expected_session_name = "initialize-user-auth"
    session_dir = sessions_root / expected_session_name
    assert session_dir.is_dir()
    assert "hello from dynamic session" in result.stdout
    assert (session_dir / "01" / "report.md").exists()


def test_teddy_start_with_explicit_name(tmp_path, monkeypatch, container):
    """
    Scenario: teddy start with explicit name does not rename.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".git").mkdir()
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")

    prompts_dir = teddy_dir / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text(
        "<prompt>test</prompt>", encoding="utf-8"
    )

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response("""# Plan: Some Other Title
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
""")
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    # Act
    result = runner.invoke(
        app, ["start", "explicit-name"], input="My prompt\ny\n", catch_exceptions=False
    )

    # Assert
    assert result.exit_code == 0
    assert (teddy_dir / "sessions" / "explicit-name").is_dir()
    assert not (teddy_dir / "sessions" / "some-other-title").exists()
