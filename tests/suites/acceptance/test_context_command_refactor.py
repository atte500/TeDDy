from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_context_creates_default_perm_context_file(tmp_path, monkeypatch):
    """Scenario: context command bootstraps project configuration on first run."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "README.md").touch()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/ARCHITECTURE.md").touch()

    result = adapter.run_cli_command(["context"], tmp_path)

    assert result.exit_code == 0
    teddy_dir = tmp_path / ".teddy"

    # Check init.context
    perm_context_file = teddy_dir / "init.context"
    assert perm_context_file.exists()
    assert "README.md" in perm_context_file.read_text(encoding="utf-8")

    # Check .gitignore
    gitignore_file = teddy_dir / ".gitignore"
    assert gitignore_file.exists()
    # The default template ignores everything in the .teddy directory
    assert "*" in gitignore_file.read_text(encoding="utf-8")


def test_context_generates_standard_output_and_is_clean(tmp_path, monkeypatch):
    """Scenario: context command generates standardized output with system info and tree."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/init.context").write_text(
        "README.md\nnon_existent_file.md\n", encoding="utf-8"
    )
    (tmp_path / "README.md").write_text("# Test README", encoding="utf-8")

    result = adapter.run_cli_command(["context"], tmp_path)
    output = result.stdout

    assert result.exit_code == 0
    assert "# Project Context" in output
    assert "## 1. System Information" in output
    assert "## 2. Git Status" in output
    assert "## 3. Project Structure" in output
    assert "## 4. Resource Contents" in output
    assert "# Test README" in output
    assert "non_existent_file.md" in output


def test_context_includes_file_contents(tmp_path, monkeypatch):
    """Scenario: context command includes contents of configured files."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/init.context").write_text("main.py\n", encoding="utf-8")
    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")

    result = adapter.run_cli_command(["context"], tmp_path)

    assert result.exit_code == 0
    assert "print('hello')" in result.stdout


def test_context_includes_git_status_when_present(tmp_path, monkeypatch):
    """Scenario: context command includes the Git Status section when available."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Mock the inspector to return a specific git status
    mock_inspector = env.get_service(IEnvironmentInspector)
    mock_git_status = " M modified_file.py\n?? untracked_file.txt"
    mock_inspector.get_git_status.return_value = mock_git_status

    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/init.context").write_text("README.md\n", encoding="utf-8")
    (tmp_path / "README.md").touch()

    result = adapter.run_cli_command(["context"], tmp_path)

    assert result.exit_code == 0
    assert "## 2. Git Status" in result.stdout
    assert " M modified_file.py" in result.stdout
    assert "?? untracked_file.txt" in result.stdout
