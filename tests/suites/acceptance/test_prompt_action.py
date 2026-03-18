from pathlib import Path
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_prompt_action_successful(tmp_path, monkeypatch):
    """Scenario 1: Successful PROMPT captures user response."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    user_response = "Blue"
    # ActionExecutor skips confirmation for PROMPT.
    # Interactive Flow:
    # 1. Skip Plan Edit: \n
    # 2. Enter Response: Blue\n
    cli_input = f"\n{user_response}\n"

    plan = (
        MarkdownPlanBuilder("Test Prompt")
        .add_prompt("What is your favorite color?")
        .build()
    )

    report = adapter.execute_plan(plan, user_input=cli_input, interactive=True)

    assert report.action_was_successful(0)
    assert report.action_logs[0].details["response"] == user_response


def test_prompt_action_multiline_editor(tmp_path, monkeypatch):
    """Scenario 2: PROMPT with external editor captures multiline response."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Resolve the mock environment injected into the real interactor
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    mock_env = env.get_service(ISystemEnvironment)

    # Configure mock environment for editor lookup and temp file creation
    mock_env.get_env.return_value = "mock_editor"
    mock_env.which.return_value = "mock_editor"

    def mock_create_temp(suffix=None):
        p = tmp_path / f"temp_editor{suffix or ''}"
        return str(p)

    mock_env.create_temp_file.side_effect = mock_create_temp

    user_response = "Line 1\nLine 2\n"
    # Interactive Flow: Skip Edit (\n), Select Editor (e\n), Submit (\n) to confirm
    cli_input = "\ne\n\n"

    plan = (
        MarkdownPlanBuilder("Test Multiline Prompt").add_prompt("Write a poem:").build()
    )

    def mock_run_editor(cmd, *args, **kwargs):
        filepath = Path(cmd[-1])  # Temp path is the last arg
        # Use the exact marker from ConsoleInteractor background launch logic
        marker = "<!-- Please enter your response above this line. -->"
        filepath.write_text(f"{user_response}\n{marker}\n", encoding="utf-8")

    mock_env.run_command.side_effect = mock_run_editor

    report = adapter.execute_plan(plan, user_input=cli_input, interactive=True)

    assert report.action_was_successful(0)
    assert report.action_logs[0].details["response"] == user_response.strip()


def test_prompt_with_reference_files_flow(tmp_path, monkeypatch):
    """Scenario 3: Reference Files in PROMPT are displayed in UI."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    ref_file = tmp_path / "context.md"
    ref_file.write_text("Context", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Ref Files Prompt")
        .add_prompt("Check this:", reference_files=["context.md"])
        .build()
    )

    # Interactive input: Skip Edit (\n), Empty Response (\n), Confirm Empty (\n)
    result = adapter.run_execute_with_plan(plan, input="\n\n\n", interactive=True)

    assert result.exit_code == 0
    assert "Reference Files:" in result.stdout
    assert "context.md" in result.stdout


def test_invoke_with_reference_files_naming(tmp_path, monkeypatch):
    """Scenario 4: Reference Files in INVOKE are displayed in UI."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    ref_file = tmp_path / "handoff.json"
    ref_file.write_text("{}", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Ref Files Invoke")
        .add_invoke("Architect", "Handoff", reference_files=["handoff.json"])
        .build()
    )

    # INVOKE/RETURN only have Skip Edit (\n) and the handoff approval (\n).
    result = adapter.run_execute_with_plan(plan, input="\n\n", interactive=True)

    assert result.exit_code == 0
    assert "Reference Files:" in result.stdout
    assert "handoff.json" in result.stdout
