from unittest.mock import MagicMock
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


def setup_project_env(tmp_path):
    (tmp_path / ".git").mkdir(exist_ok=True)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test Project", encoding="utf-8")
    prompts_dir = teddy_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text("<prompt/>", encoding="utf-8")


def test_resume_auto_detects_latest_session(tmp_path, monkeypatch, container):
    """
    Given several sessions exist in .teddy/sessions/.
    When I run 'teddy resume' from the project root without arguments.
    Then it MUST automatically pick the most recently modified session.
    """
    monkeypatch.chdir(tmp_path)
    setup_project_env(tmp_path)

    valid_plan = """# Plan: Test
- Status: Green 🟢
- Plan Type: Testing
- Agent: Pathfinder

## Rationale
````
### 1. Synthesis
OK
### 2. Justification
OK
### 3. Expected Outcome
OK
### 4. State Dashboard
OK
````

## Action Plan
### `EXECUTE`
- Description: test
````shell
echo 'ok'
````
"""

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(valid_plan)
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    # 1. Create two sessions
    runner.invoke(app, ["start", "older-session"], input="prompt\ny\n")
    # Wait a second to ensure different timestamps if fs resolution is low
    import time

    time.sleep(1.1)
    runner.invoke(app, ["start", "newer-session"], input="prompt\ny\n")

    # 2. Run resume from root
    # Provide multiple inputs to handle potential planning + execution prompts
    result = runner.invoke(
        app, ["resume"], input="prompt\ny\ny\ny\n", catch_exceptions=False
    )

    assert result.exit_code == 0
    # Orchestrator will print "Resuming session: newer-session" or similar
    assert "newer-session" in result.stdout
    assert "older-session" not in result.stdout


def test_resume_with_session_path(tmp_path, monkeypatch, container):
    """
    Given a session exists.
    When I run 'teddy resume .teddy/sessions/my-session'.
    Then it MUST resolve and resume that session.
    """
    monkeypatch.chdir(tmp_path)
    setup_project_env(tmp_path)

    valid_plan = """# Plan: Test
- Status: Green 🟢
- Plan Type: Testing
- Agent: Pathfinder

## Rationale
````
### 1. Synthesis
OK
### 2. Justification
OK
### 3. Expected Outcome
OK
### 4. State Dashboard
OK
````

## Action Plan
### `EXECUTE`
- Description: test
````shell
echo 'ok'
````
"""

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(valid_plan)
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    runner.invoke(app, ["start", "my-session"], input="prompt\ny\n")

    result = runner.invoke(
        app,
        ["resume", ".teddy/sessions/my-session"],
        input="prompt\ny\ny\ny\n",
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_resume_with_turn_path(tmp_path, monkeypatch, container):
    """
    Given a session exists with a turn.
    When I run 'teddy resume .teddy/sessions/my-session/01'.
    Then it MUST resolve the session name and resume it.
    """
    monkeypatch.chdir(tmp_path)
    setup_project_env(tmp_path)

    valid_plan = """# Plan: Test
- Status: Green 🟢
- Plan Type: Testing
- Agent: Pathfinder

## Rationale
````
### 1. Synthesis
OK
### 2. Justification
OK
### 3. Expected Outcome
OK
### 4. State Dashboard
OK
````

## Action Plan
### `EXECUTE`
- Description: test
````shell
echo 'ok'
````
"""

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(valid_plan)
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    runner.invoke(app, ["start", "my-session"], input="prompt\ny\n")

    result = runner.invoke(
        app,
        ["resume", ".teddy/sessions/my-session/01"],
        input="prompt\ny\ny\ny\n",
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout


def test_resume_with_file_path(tmp_path, monkeypatch, container):
    """
    Given a session exists with a file.
    When I run 'teddy resume .teddy/sessions/my-session/01/meta.yaml'.
    Then it MUST resolve the session name and resume it.
    """
    monkeypatch.chdir(tmp_path)
    setup_project_env(tmp_path)

    valid_plan = """# Plan: Test
- Status: Green 🟢
- Plan Type: Testing
- Agent: Pathfinder

## Rationale
````
### 1. Synthesis
OK
### 2. Justification
OK
### 3. Expected Outcome
OK
### 4. State Dashboard
OK
````

## Action Plan
### `EXECUTE`
- Description: test
````shell
echo 'ok'
````
"""

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(valid_plan)
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    runner.invoke(app, ["start", "my-session"], input="prompt\ny\n")

    result = runner.invoke(
        app,
        ["resume", ".teddy/sessions/my-session/01/meta.yaml"],
        input="prompt\ny\ny\ny\n",
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "my-session" in result.stdout
