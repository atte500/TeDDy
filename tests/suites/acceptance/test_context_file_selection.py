from pathlib import Path

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _seed_context_workspace(tmp_path: Path) -> None:
    """Seeds an init.context default set and one explicit-only file."""
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "init.context").write_text("README.md\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Default README\n", encoding="utf-8")
    (tmp_path / "extra.py").write_text("# Explicit extra\n", encoding="utf-8")


def test_context_command_merges_explicit_file_with_init_context(
    tmp_path: Path, monkeypatch
) -> None:
    """An explicit -c path extends the default init.context set."""
    TestEnvironment(
        monkeypatch, tmp_path
    ).setup().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _seed_context_workspace(tmp_path)

    result = adapter.run_cli_command(
        ["context", "--no-copy", "-c", "extra.py"], tmp_path
    )

    assert result.exit_code == 0, result.stdout
    assert "### [README.md](/README.md)" in result.stdout
    assert "### [extra.py](/extra.py)" in result.stdout
