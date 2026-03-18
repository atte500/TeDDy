from pathlib import Path
from unittest.mock import MagicMock
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.drivers.cli_adapter import CliTestAdapter
from tests.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import ILlmClient


def mock_response(content):
    res = MagicMock()
    res.choices = [MagicMock()]
    res.choices[0].message.content = content
    res.model = "gpt-4"
    return res


def setup_project(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    teddy = tmp_path / ".teddy"
    teddy.mkdir()
    (teddy / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("README", encoding="utf-8")
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "pathfinder.xml").write_text(
        "<prompt>Pathfinder</prompt>", encoding="utf-8"
    )


def test_teddy_start_bootstraps_session(tmp_path: Path, monkeypatch):
    """Scenario: 'start' command creates session structure and bootstraps context."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["start", "feat-x"], input="instructions\ny\n")
    assert result.exit_code == 0

    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    assert (session_dir / "01" / "meta.yaml").exists()
    assert (session_dir / "session.context").read_text().strip() == "README.md"
    assert "Pathfinder" in (session_dir / "01" / "pathfinder.xml").read_text()


def test_teddy_plan_injects_turn_1_hint(tmp_path: Path, monkeypatch):
    """Scenario: 'plan' command injects alignment hint for the first turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "hint-test" / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    result = adapter.run_cli_command(["plan", "-m", "Do stuff"], cwd=turn_dir)
    assert result.exit_code == 0

    args, kwargs = llm.get_completion.call_args  # type: ignore[attr-defined]
    sent = kwargs["messages"][1]["content"]
    assert "Do stuff" in sent and "aligned" in sent.lower()


def test_teddy_resume_executes_pending_plan(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' executes an existing plan if one is pending."""
    (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "resume" / "01"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '01'")

    plan = MarkdownPlanBuilder("Resume").add_execute("echo hello").build()
    (turn_dir / "plan.md").write_text(plan, encoding="utf-8")

    result = adapter.run_cli_command(["resume", "-y"], cwd=turn_dir)
    assert result.exit_code == 0
    assert "hello" in result.stdout
    assert (turn_dir / "report.md").exists()
    assert (turn_dir.parent / "02").exists()


def test_teddy_resume_prompts_for_new_plan(tmp_path: Path, monkeypatch):
    """Scenario: 'resume' prompts for input if no plan exists for the current turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    turn_dir = tmp_path / ".teddy" / "sessions" / "resume-new" / "02"
    turn_dir.mkdir(parents=True)
    (turn_dir.parent / "session.context").touch()
    (turn_dir / "turn.context").touch()
    (turn_dir / "pathfinder.xml").touch()
    (turn_dir / "meta.yaml").write_text("turn_id: '02'\nparent_turn_id: '01'")

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("New").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["resume"], cwd=turn_dir, input="My Goal\n")
    assert result.exit_code == 0

    assert (turn_dir / "plan.md").exists()
    sent = llm.get_completion.call_args[1]["messages"][1]["content"]  # type: ignore[attr-defined]
    assert "My Goal" in sent and "alignment" in sent


def test_teddy_start_dynamic_renaming_and_flow(tmp_path: Path, monkeypatch):
    """Scenario: Session is dynamically renamed based on the generated plan title."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Auth Feature").add_execute("echo 'auth'").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["start"], input="My prompt\ny\n")
    assert result.exit_code == 0

    assert (
        tmp_path / ".teddy" / "sessions" / "auth-feature" / "01" / "report.md"
    ).exists()


def test_teddy_start_with_explicit_name(tmp_path: Path, monkeypatch):
    """Scenario: 'start' with an explicit name disables dynamic renaming."""
    env = (
        TestEnvironment(monkeypatch, tmp_path)
        .setup()
        .with_real_shell()
        .with_real_interactor()
    )
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)  # type: ignore[type-abstract]
    plan = MarkdownPlanBuilder("Other").add_execute("echo '1'").build()
    llm.get_completion.return_value = mock_response(plan)  # type: ignore[attr-defined]

    result = adapter.run_cli_command(["start", "fixed-name"], input="prompt\ny\n")
    assert result.exit_code == 0

    assert (tmp_path / ".teddy" / "sessions" / "fixed-name").exists()
    assert not (tmp_path / ".teddy" / "sessions" / "other").exists()
