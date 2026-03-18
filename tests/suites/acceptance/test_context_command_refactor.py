from pathlib import Path
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_context_creates_default_perm_context_file(tmp_path, monkeypatch):
    """Scenario: context command bootstraps project configuration on first run."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
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
    source_context = (Path(__file__).parents[3] / "config" / "init.context").read_text(
        encoding="utf-8"
    )
    assert perm_context_file.read_text() == source_context

    # Check .gitignore
    gitignore_file = teddy_dir / ".gitignore"
    assert gitignore_file.exists()
    source_gitignore = (Path(__file__).parents[3] / "config" / ".gitignore").read_text(
        encoding="utf-8"
    )
    assert gitignore_file.read_text() == source_gitignore


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
    assert "# System Information" in output
    assert "# Repository Tree" in output
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
