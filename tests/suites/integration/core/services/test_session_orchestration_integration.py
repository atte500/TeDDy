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


def test_teddy_context_aggregates_cascading_context(tmp_path, monkeypatch):
    """
    Scenario: teddy context aggregates cascading context
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "file_a.py").write_text("content_a", encoding="utf-8")
    (tmp_path / "file_b.py").write_text("content_b", encoding="utf-8")

    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("file_a.py", encoding="utf-8")
    (turn_dir / "turn.context").write_text("file_b.py", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    monkeypatch.chdir(turn_dir)
    result = runner.invoke(app, ["context", "--no-copy"])

    assert result.exit_code == 0
    assert "content_a" in result.stdout
    assert "content_b" in result.stdout
    assert "### Turn" in result.stdout
    assert "file_b.py" in result.stdout
    assert "### Session" in result.stdout
    assert "file_a.py" in result.stdout


def test_teddy_execute_triggers_turn_transition(tmp_path, monkeypatch):
    """
    Scenario: teddy execute triggers turn transition
    """
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text("prompt_content", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text(
        "turn_id: 'abc'\nagent_name: 'pathfinder'\n", encoding="utf-8"
    )

    (tmp_path / "new_file.py").write_text("print('hello')", encoding="utf-8")

    plan_content = """# Plan: Read a file
- Status: Green 🟢
- Plan Type: Testing
- Agent: Developer

## Rationale
```
Testing turn transition.
```

## Action Plan
### `READ`
- **Resource:** [new_file.py](/new_file.py)
"""
    plan_file = turn_dir / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")

    result = runner.invoke(
        app, ["execute", str(plan_file.relative_to(tmp_path)), "-y", "--no-copy"]
    )

    assert result.exit_code == 0
    next_turn_dir = session_dir / "02"
    assert next_turn_dir.is_dir()
    turn_context_content = (next_turn_dir / "turn.context").read_text(encoding="utf-8")
    assert "new_file.py" in turn_context_content
    assert "01/report.md" in turn_context_content

    with open(next_turn_dir / "meta.yaml", "r", encoding="utf-8") as f:
        meta_data = yaml.safe_load(f)
        assert meta_data["parent_turn_id"] == "abc"
        assert meta_data["turn_id"] == "02"


def test_teddy_plan_generates_plan_file(tmp_path, monkeypatch, container):
    """
    Scenario: teddy plan generates a plan
    """
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text("system prompt", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    mock_llm = MagicMock(spec=ILlmClient)
    mock_llm.get_completion.return_value = make_mock_response(
        "# Plan: Generated Plan\n- Status: Green 🟢"
    )
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    monkeypatch.chdir(turn_dir)
    result = runner.invoke(app, ["plan", "-m", "Implement feature X"])

    assert result.exit_code == 0
    plan_file = turn_dir / "plan.md"
    assert plan_file.exists()
    assert "# Plan: Generated Plan" in plan_file.read_text(encoding="utf-8")
