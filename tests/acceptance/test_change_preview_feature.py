from pathlib import Path
from teddy_executor.core.ports.outbound import ISystemEnvironment, IUserInteractor
from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.observers.report_parser import ReportParser


def test_in_terminal_diff_is_shown_for_create_file(tmp_path: Path, monkeypatch):
    """Scenario: CREATE action shows in-terminal preview."""
    import punq
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    mock_env = env.get_service(ISystemEnvironment)  # type: ignore[type-abstract]
    # Properly wire the REAL interactor. Must be transient to override the container's default.
    env._container.register(
        IUserInteractor,
        factory=lambda: ConsoleInteractorAdapter(mock_env),
        scope=punq.Scope.transient,
    )
    mock_env.get_env.return_value = None  # type: ignore[attr-defined]
    mock_env.which.return_value = None  # type: ignore[attr-defined]

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "new_file.txt"
    file_content = "First line.\nSecond line.\n"
    plan = (
        MarkdownPlanBuilder("Test Create with Diff")
        .add_create(filename, file_content)
        .build()
    )

    # GIVEN: No diff tool is configured
    mock_env.get_env.return_value = ""  # type: ignore[attr-defined]
    mock_env.which.return_value = None  # type: ignore[attr-defined]

    # WHEN: Executed interactively
    result = adapter.run_command(
        ["execute", "--no-copy", "--plan-content", plan], input="y\n"
    )

    # THEN: Success and file created
    assert result.exit_code == 0
    assert (tmp_path / filename).exists()
    report = ReportParser(result.stdout)
    assert report.run_summary["Overall Status"] == "SUCCESS"

    # AND THEN: Preview shown in captured output
    combined_output = result.stdout + (result.stderr or "")
    assert "--- New File Preview ---" in combined_output
    assert f"Path: {filename}" in combined_output
    assert "First line." in combined_output
    assert "Approve? (y/n):" in combined_output


def test_in_terminal_diff_is_shown_as_fallback(tmp_path: Path, monkeypatch):
    """Scenario: EDIT action shows in-terminal diff fallback."""
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    mock_env = env.get_service(ISystemEnvironment)  # type: ignore[type-abstract]
    # Re-register the REAL interactor for diff preview tests
    interactor = ConsoleInteractorAdapter(mock_env)
    env._container.register(IUserInteractor, instance=interactor)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "hello.txt"
    (tmp_path / filename).write_text("Hello, world!", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Test Edit with Diff")
        .add_edit(filename, "world", "TeDDy")
        .build()
    )

    mock_env.get_env.return_value = ""  # type: ignore[attr-defined]
    mock_env.which.return_value = None  # type: ignore[attr-defined]

    result = adapter.run_command(
        ["execute", "--no-copy", "--plan-content", plan], input="y\n"
    )

    assert result.exit_code == 0
    assert (tmp_path / filename).read_text() == "Hello, TeDDy!"
    combined_output = result.stdout + (result.stderr or "")
    assert "--- Diff ---" in combined_output
    assert "-Hello, world!" in combined_output
    assert "+Hello, TeDDy!" in combined_output


def test_vscode_is_used_as_fallback(tmp_path: Path, monkeypatch):
    """Scenario: VS Code is used for diffing when available."""
    import punq
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    mock_env = env.get_service(ISystemEnvironment)  # type: ignore[type-abstract]
    # Properly wire the REAL interactor
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )

    env._container.register(
        IUserInteractor,
        factory=lambda: ConsoleInteractorAdapter(mock_env),
        scope=punq.Scope.transient,
    )

    mock_env.get_env.return_value = None  # type: ignore[attr-defined]
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "hello.txt"
    (tmp_path / filename).write_text("Hello, world!", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Test VSCode Fallback")
        .add_edit(filename, "world", "TeDDy")
        .build()
    )

    mock_env.get_env.return_value = ""  # type: ignore[attr-defined]
    mock_env.which.side_effect = lambda cmd: "/usr/bin/code" if cmd == "code" else None  # type: ignore[attr-defined]
    mock_env.create_temp_file.side_effect = lambda suffix: str(  # type: ignore[attr-defined]
        tmp_path / f"temp{suffix}"
    )

    result = adapter.run_command(
        ["execute", "--no-copy", "--plan-content", plan], input="y\n"
    )

    assert result.exit_code == 0
    mock_env.run_command.assert_called_once()  # type: ignore[attr-defined]
    cmd = mock_env.run_command.call_args[0][0]  # type: ignore[attr-defined]
    assert cmd[0] == "/usr/bin/code"
    assert "--diff" in cmd


def test_custom_diff_tool_is_used_from_env(tmp_path: Path, monkeypatch):
    """Scenario: Custom diff tool from env is used."""
    import punq
    from teddy_executor.core.ports.outbound import ISystemEnvironment

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    mock_env = env.get_service(ISystemEnvironment)  # type: ignore[type-abstract]
    # Properly wire the REAL interactor
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )

    env._container.register(
        IUserInteractor,
        factory=lambda: ConsoleInteractorAdapter(mock_env),
        scope=punq.Scope.transient,
    )

    mock_env.get_env.return_value = None  # type: ignore[attr-defined]
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "hello.txt"
    (tmp_path / filename).write_text("Hello, world!", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Test Custom Diff Tool")
        .add_edit(filename, "world", "TeDDy")
        .build()
    )

    mock_env.get_env.return_value = "nvim -d"  # type: ignore[attr-defined]
    mock_env.which.side_effect = lambda cmd: "/usr/bin/nvim" if cmd == "nvim" else None  # type: ignore[attr-defined]
    mock_env.create_temp_file.side_effect = lambda suffix: str(  # type: ignore[attr-defined]
        tmp_path / f"temp{suffix}"
    )

    adapter.run_command(["execute", "--no-copy", "--plan-content", plan], input="y\n")

    mock_env.run_command.assert_called_once()  # type: ignore[attr-defined]
    cmd = mock_env.run_command.call_args[0][0]  # type: ignore[attr-defined]
    assert cmd[0] == "/usr/bin/nvim"
    assert cmd[1] == "-d"


def test_invalid_custom_tool_falls_back_to_terminal(tmp_path: Path, monkeypatch):
    """Scenario: Invalid custom tool falls back to terminal diff."""
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    mock_env = env.get_service(ISystemEnvironment)  # type: ignore[type-abstract]
    # Re-register the REAL interactor for diff preview tests
    interactor = ConsoleInteractorAdapter(mock_env)
    env._container.register(IUserInteractor, instance=interactor)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "hello.txt"
    (tmp_path / filename).write_text("Hello!")

    plan = (
        MarkdownPlanBuilder("Test Invalid Tool Fallback")
        .add_edit(filename, "!", ", TeDDy!")
        .build()
    )

    mock_env.get_env.return_value = "nonexistent-tool"  # type: ignore[attr-defined]
    mock_env.which.side_effect = lambda cmd: "/usr/bin/code" if cmd == "code" else None  # type: ignore[attr-defined]

    result = adapter.run_command(
        ["execute", "--no-copy", "--plan-content", plan], input="y\n"
    )

    combined_output = result.stdout + result.stderr
    assert result.exit_code == 0
    assert "--- a/hello.txt" in combined_output
    assert "Warning: Custom diff tool 'nonexistent-tool' not found" in combined_output
    mock_env.run_command.assert_not_called()  # type: ignore[attr-defined]


def test_no_diff_is_shown_for_auto_approved_plans(tmp_path: Path, monkeypatch):
    """Scenario: No diff shown when --yes is used."""
    from unittest.mock import Mock

    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()

    # Manually register a mock interactor to verify it's NOT used
    mock_interactor = Mock(spec=IUserInteractor)
    env._container.register(IUserInteractor, instance=mock_interactor)

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    filename = "hello.txt"
    (tmp_path / filename).write_text("Hello, world!", encoding="utf-8")
    plan = (
        MarkdownPlanBuilder("Test No Diff on Auto-Approve")
        .add_edit(filename, "world", "TeDDy")
        .build()
    )

    result = adapter.run_command(
        ["execute", "--yes", "--no-copy", "--plan-content", plan]
    )

    assert result.exit_code == 0
    assert (tmp_path / filename).read_text() == "Hello, TeDDy!"
    mock_interactor.confirm_action.assert_not_called()
    assert "--- Diff ---" not in result.stdout
