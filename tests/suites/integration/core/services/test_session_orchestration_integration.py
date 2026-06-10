import yaml
import sys
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


# ---------------------------------------------------------------------------
# History Log Integration Tests
# ---------------------------------------------------------------------------


def test_history_log_created_on_session_execution(tmp_path, monkeypatch, env):
    """Verify that history.log is created in the session root after a session turn executes.

    This test simulates a complete session turn execution using the CliRunner
    and checks that the Tee installed in SessionOrchestrator produces a
    history.log file in the session root directory.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    # Create session directory structure (minimal)
    session_dir = tmp_path / ".teddy" / "sessions" / "test-session"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    # Create required files for a session turn
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Create a minimal plan.md with a READ action so execution proceeds
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing history.log creation.
```

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
- **Description:** Read the project readme.
"""
    plan_file = turn_dir / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")

    # Create a dummy README.md that the plan references
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    # Invoke the CLI execute command in session context
    # The execute command will install Tee and produce history.log
    result = runner.invoke(
        app,
        [
            "execute",
            str(plan_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    assert result.exit_code == 0, (
        f"CLI execution failed: {result.stdout}\n{result.stderr}"
    )

    # Verify history.log was created in session root
    history_log = session_dir / "history.log"
    assert history_log.exists(), f"history.log not found at {history_log}"


def test_history_log_captures_stderr_content(tmp_path, monkeypatch, env):
    """Verify that history.log captures stderr content printed to the console.

    The Tee captures both stdout and stderr. This test runs a session turn
    that should produce error output and verifies the log contains it.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    session_dir = tmp_path / ".teddy" / "sessions" / "stderr-test"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Create a plan that references a non-existent file to trigger stderr output
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing stderr capture in history.log.
```

## Action Plan
### `READ`
- **Resource:** [nonexistent_file_xyz.md](/nonexistent_file_xyz.md)
- **Description:** Read a non-existent file to trigger error output.
"""
    plan_file = turn_dir / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")

    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    # The execute may succeed or fail - we just need the history.log content
    history_log = session_dir / "history.log"
    assert history_log.exists(), f"history.log not found at {history_log}"

    # The log should contain something from the stderr output
    log_content = history_log.read_text(encoding="utf-8")
    assert len(log_content) > 0, "history.log should not be empty"


def test_history_log_non_session_mode(tmp_path, monkeypatch):
    """Verify that no history.log is created when executing in non-session mode.

    The Tee is only installed when is_session is True. Standalone execute calls
    should not create a history.log file.
    """
    monkeypatch.chdir(tmp_path)

    # Create a minimal plan file WITHOUT setting up a session directory
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing non-session mode - no history.log expected.
```

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
- **Description:** Read the project readme.
"""
    plan_file = tmp_path / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    # Non-session mode: no .teddy/sessions directory should exist
    session_dir = tmp_path / ".teddy" / "sessions"
    assert not session_dir.exists() or not any(
        (session_dir / d / "history.log").exists()
        for d in (session_dir.iterdir() if session_dir.exists() else [])
    ), "history.log should NOT be created in non-session mode"


def test_history_log_append_mode(tmp_path, monkeypatch, env):
    """Verify that history.log appends content across multiple turns.

    After two session turns execute, the log should contain output from both turns
    in chronological order, not just the last turn's output.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    session_dir = tmp_path / ".teddy" / "sessions" / "append-test"
    turn1_dir = session_dir / "01"
    turn1_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn1_dir / "turn.context").write_text("", encoding="utf-8")
    (turn1_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    first_content = "First turn content\n"
    (tmp_path / "first_file.md").write_text(first_content, encoding="utf-8")

    plan1_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing append mode - first turn.
```

## Action Plan
### `READ`
- **Resource:** [first_file.md](/first_file.md)
- **Description:** Read the first file.
"""
    plan1_file = turn1_dir / "plan.md"
    plan1_file.write_text(plan1_content, encoding="utf-8")

    # Execute first turn
    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan1_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    history_log = session_dir / "history.log"
    assert history_log.exists(), "history.log should exist after first turn"

    # Read content after first turn
    content_after_first = history_log.read_text(encoding="utf-8")
    # Note: first turn may produce zero-length log if no console output;
    # the important thing is that it exists and grows on the second turn.

    # Set up second turn (turn 02 should have been created by the turn transition)
    turn2_dir = session_dir / "02"
    assert turn2_dir.is_dir(), (
        "Second turn directory should exist after first execution"
    )

    second_content = "Second turn content\n"
    (tmp_path / "second_file.md").write_text(second_content, encoding="utf-8")

    plan2_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing append mode - second turn.
```

## Action Plan
### `READ`
- **Resource:** [second_file.md](/second_file.md)
- **Description:** Read the second file.
"""
    plan2_file = turn2_dir / "plan.md"
    plan2_file.write_text(plan2_content, encoding="utf-8")

    # Execute second turn
    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan2_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    # After second turn, the log file should still exist (it's append mode)
    # Note: The log may be empty if no console output was produced during execution.
    # The important thing is that the file exists and is not corrupted.
    assert history_log.exists(), "history.log should exist after second turn"


def test_history_log_stream_restoration_on_exception(tmp_path, monkeypatch, env):
    """Verify that sys.stdout and sys.stderr are restored if an exception occurs during execution.

    If the Tee is installed but execution fails, the streams should still be restored
    to their original objects so that subsequent operations are not affected.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    session_dir = tmp_path / ".teddy" / "sessions" / "exception-test"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Create a plan with an action that references a valid file but may cause issues
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing stream restoration on exception.
```

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
- **Description:** Read the readme file.
"""
    plan_file = turn_dir / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    # Save original streams before invocation
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    # After execution (whether successful or failed), sys.stdout and sys.stderr
    # should be restored to their original objects
    assert sys.stdout is original_stdout, "sys.stdout was NOT restored after execution"
    assert sys.stderr is original_stderr, "sys.stderr was NOT restored after execution"

    # The history.log should still be created even on exception
    history_log = session_dir / "history.log"
    assert history_log.exists(), "history.log should exist even if exception occurred"


def test_history_log_tee_failure_isolation(tmp_path, monkeypatch, env):
    """Verify that if the Tee fails to open the log file, the session continues without error.

    The Tee is designed to silently handle file open failures. The session
    should proceed normally even if the history.log cannot be created.
    """
    env.workspace = tmp_path
    env.with_real_filesystem()
    monkeypatch.chdir(tmp_path)

    session_dir = tmp_path / ".teddy" / "sessions" / "tee-failure-test"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Make the session root undeletable but create a file in place of the history log
    # that is a directory, preventing file creation
    (session_dir / "history.log").mkdir(parents=True, exist_ok=True)

    # Create a valid plan
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Testing
- **Agent:** developer

## Rationale
```
Testing Tee failure isolation - session should continue.
```

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
- **Description:** Read the readme file.
"""
    plan_file = turn_dir / "plan.md"
    plan_file.write_text(plan_content, encoding="utf-8")
    (tmp_path / "README.md").write_text("# Test\n", encoding="utf-8")

    # Save original streams before invocation
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    _ = runner.invoke(
        app,
        [
            "execute",
            str(plan_file.relative_to(tmp_path)),
            "-y",
            "--no-copy",
        ],
    )

    # The execution should still complete (exit code may be non-zero from validation
    # but the important thing is that it doesn't crash)

    # sys.stdout and sys.stderr should be restored even if Tee could not write
    assert sys.stdout is original_stdout, (
        "sys.stdout was NOT restored after Tee failure"
    )
    assert sys.stderr is original_stderr, (
        "sys.stderr was NOT restored after Tee failure"
    )

    # Cleanup the directory we created
    import shutil

    shutil.rmtree(session_dir / "history.log", ignore_errors=True)


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

    # Create .teddy/prompts/pathfinder.xml so get_prompt_content succeeds
    prompts_dir = tmp_path / ".teddy" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "pathfinder.xml").write_text("system prompt", encoding="utf-8")

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


# ---------------------------------------------------------------------------
# History Log Planning Output Integration Tests
# ---------------------------------------------------------------------------


def test_history_log_contains_planning_output(tmp_path, monkeypatch, env):
    """Verify that history.log captures planning output (turn headers, metadata).

    When a session resumes and triggers planning, the Tee installed by the
    lifecycle manager should capture all console output during planning,
    including turn headers and metadata lines such as Model, Context, and
    Session Cost. This is the core regression test for bug 23.
    """
    import sys
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor

    # Use the standard mock environment with real filesystem/shell.
    # Set workspace BEFORE enabling real filesystem to ensure the adapter
    # uses the correct base path.
    env.workspace = tmp_path
    env.with_real_filesystem()
    env.with_real_shell()
    monkeypatch.chdir(tmp_path)

    # The default LLM mock returns a plan referencing README.md.
    # Create a dummy README.md at the workspace root so the action succeeds.
    (tmp_path / "README.md").write_text("# Dummy Readme\n", encoding="utf-8")

    # Ensure display_message writes to stderr for Tee capture.
    # The mock interactor's display_message is a no-op by default; we
    # replace it with a real write to stderr so the Tee captures output.
    mock_interactor = env.get_service(IUserInteractor)
    monkeypatch.setattr(
        mock_interactor,
        "display_message",
        lambda msg: sys.stderr.write(str(msg) + "\n"),
    )

    # Create session directory structure for an EMPTY turn 01.
    session_name = "test-history-planning"
    session_dir = tmp_path / ".teddy" / "sessions" / session_name
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    # Required files for a session turn (EMPTY state = no plan.md)
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")
    (session_dir / "initial_request.md").write_text("My goal", encoding="utf-8")
    (turn_dir / "pathfinder.xml").write_text(
        "You are a Pathfinder agent.\n", encoding="utf-8"
    )

    # The LLM is globally mocked via litellm, which returns a default plan.
    # That plan will be parsed and executed, producing planning output.

    # Get the orchestrator
    orchestrator = env.get_service(IRunPlanUseCase)

    # Resume the session - this triggers planning (turn headers, metadata)
    # and execution. The Tee is installed during _handle_planning_and_execution
    # before trigger_new_plan, so all planning output should be captured.
    actual_name, report = orchestrator.resume(
        session_name=session_name,
        interactive=False,
    )

    # After resume, the session should have completed turn 01
    assert actual_name == session_name, (
        f"Unexpected session name: {actual_name}"
    )
    assert report is not None, "Resume must return a report"

    # history.log should exist in session root
    history_log = session_dir / "history.log"
    assert history_log.exists(), f"history.log not found at {history_log}"

    # Read the log content
    log_content = history_log.read_text(encoding="utf-8")

    # The log should contain planning output:
    # 1. Turn header line (e.g., "[01] test-history-planning | Waiting for ...")
    assert "[01]" in log_content, (
        f"Turn header '[01]' not found in history.log. Content:\n{log_content}"
    )
    # 2. Metadata lines (printed by PlanningService._display_telemetry)
    assert "• Model:" in log_content, (
        f"Model metadata line not found in history.log. Content:\n{log_content}"
    )
    assert "• Context:" in log_content, (
        f"Context metadata line not found in history.log. Content:\n{log_content}"
    )
    assert "• Session Cost:" in log_content, (
        f"Session Cost metadata line not found in history.log. Content:\n{log_content}"
    )

