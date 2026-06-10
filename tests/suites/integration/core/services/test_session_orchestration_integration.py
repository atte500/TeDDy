import yaml
from tests.harness.setup.mocking import POSIXPathMock
from typer.testing import CliRunner
from teddy_executor.__main__ import app
from teddy_executor.core.ports.outbound.llm_client import ILlmClient

runner = CliRunner()


def make_mock_response(content, model="gpt-4o"):
    mock_response = POSIXPathMock()
    mock_response.model = model
    mock_message = POSIXPathMock()
    mock_message.content = content
    mock_choice = POSIXPathMock()
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
    assert "file_b.py" in result.stdout
    assert "file_a.py" in result.stdout


def test_teddy_execute_triggers_turn_transition(tmp_path, monkeypatch, env):
    """
    Scenario: teddy execute triggers turn transition
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
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


def test_teddy_plan_generates_plan_file(tmp_path, monkeypatch, env):
    """
    Scenario: teddy plan generates a plan
    """
    env.with_real_filesystem()
    container = env.container
    monkeypatch.chdir(tmp_path)
    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text("system prompt", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    mock_llm = POSIXPathMock()
    mock_llm.validate_config.return_value = []
    mock_llm.get_completion.return_value = make_mock_response(
        "# Plan: Generated Plan\n- Status: Green 🟢"
    )
    mock_llm.get_token_count.return_value = 100
    mock_llm.get_completion_cost.return_value = 0.01
    container.register(ILlmClient, instance=mock_llm)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_plan_generation,
    )

    monkeypatch.chdir(turn_dir)
    handle_plan_generation(container, "Implement feature X")

    plan_file = turn_dir / "plan.md"
    assert plan_file.exists()
    assert "# Plan: Generated Plan" in plan_file.read_text(encoding="utf-8")


def test_centennial_migration_resume_loop_continuation(tmp_path, monkeypatch, env):
    """
    Scenario: Resume loop correctly updates session_name after centennial migration.

    Given a session with turn 99 completed,
    When resume() is called with the original session name,
    Then it returns (continuation_name, report) and creates the continuation session.
    When resume() is called again with the continuation session name,
    Then it processes the pending plan without triggering another migration.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    # Mock the LLM to return a plan for the continuation turn's planning step
    plan_content = """# Plan: Continuation Turn
- Status: Green 🟢
- Plan Type: TEST
- Agent: developer

## Rationale
```
Testing centennial migration resume loop.
```

## Action Plan
### `EXECUTE`
- **Command:** echo "migration-test-ok"
"""
    llm_client = env.get_service(ILlmClient)
    llm_client.get_completion.return_value = make_mock_response(plan_content)

    # Build a session with turn 99 completed (report.md exists)
    session_name = "test-migration"
    session_dir = tmp_path / ".teddy" / "sessions" / session_name
    turn_99 = session_dir / "99"
    turn_99.mkdir(parents=True)

    (turn_99 / "report.md").write_text(
        "# Report\n## Turn Summary\nSUCCESS\n", encoding="utf-8"
    )
    (turn_99 / "meta.yaml").write_text(
        "turn_id: '99'\nagent_name: 'developer'\n", encoding="utf-8"
    )
    (turn_99 / "plan.md").write_text("# Plan: Previous\n", encoding="utf-8")
    (turn_99 / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")

    # Resolve the SessionOrchestrator
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase

    orchestrator = env.get_service(IRunPlanUseCase)

    # ---- First resume call ----
    # Should detect COMPLETE_TURN at turn 99, migrate to continuation session,
    # plan and execute turn 01 of the continuation session.
    actual_name, report = orchestrator.resume(
        session_name=session_name,
        interactive=False,
    )

    # Verify migration occurred
    assert actual_name == "test-migration-2", (
        f"Expected continuation name 'test-migration-2', got '{actual_name}'"
    )
    assert report is not None, "First resume call must return a report"

    # Verify continuation session directory exists with a completed turn 01
    cont_session_dir = session_dir.parent / "test-migration-2"
    assert cont_session_dir.is_dir(), "Continuation session directory must exist"
    turn_01 = cont_session_dir / "01"
    assert turn_01.is_dir(), "Continuation session must have turn 01"
    assert (turn_01 / "report.md").is_file(), (
        "Turn 01 must have a report (plan was executed)"
    )

    # ---- Second resume call with UPDATED session name ----
    # This simulates what _orchestrate_session_loop does after unpacking
    # the tuple from the first resume() call.
    second_name, second_report = orchestrator.resume(
        session_name=actual_name,
        interactive=False,
    )

    # Verify normal progression (no re-migration)
    assert second_name == actual_name, (
        f"Session name should remain '{actual_name}', got '{second_name}'"
    )
    assert second_report is not None, "Second resume call must return a report"

    # Verify turn 02 exists (showing the continuation session progressed)
    turn_02 = cont_session_dir / "02"
    assert turn_02.is_dir(), "Continuation session must have progressed to turn 02"
    assert (turn_02 / "report.md").is_file(), "Turn 02 must have a report"

    # Verify the old session is unchanged (still at turn 99)
    assert (session_dir / "99" / "report.md").is_file(), (
        "Old session turn 99 must still have its report (unchanged)"
    )
    # No new turns should exist in the old session
    old_turns = sorted(d.name for d in session_dir.iterdir() if d.name.isdigit())
    assert old_turns == ["99"], f"Old session should only have turn 99, got {old_turns}"
    # Only one continuation session should exist
    cont_dirs = sorted(
        d.name
        for d in session_dir.parent.iterdir()
        if d.name.startswith("test-migration") and d.name != "test-migration"
    )
    assert cont_dirs == ["test-migration-2"], (
        f"Only one continuation session should exist, got {cont_dirs}"
    )
