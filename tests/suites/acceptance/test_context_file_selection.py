from pathlib import Path
from typing import Optional

from typer.testing import Result

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def _run_context(
    monkeypatch, tmp_path: Path, args: list[str], cwd: Optional[Path] = None
) -> Result:
    """Drives the context command against a real filesystem and init service."""
    TestEnvironment(
        monkeypatch, tmp_path
    ).setup().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    return adapter.run_cli_command(["context", "--no-copy", *args], cwd or tmp_path)


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
    _seed_context_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["-c", "extra.py"])

    assert result.exit_code == 0, result.stdout
    assert "### [README.md](/README.md)" in result.stdout
    assert "### [extra.py](/extra.py)" in result.stdout


def _seed_session_workspace(tmp_path: Path) -> Path:
    """Seeds a session turn directory with turn, session, and explicit files."""
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "init.context").write_text("README.md\n", encoding="utf-8")

    session_root = teddy_dir / "sessions" / "20260101_000000-demo"
    turn_dir = session_root / "01"
    turn_dir.mkdir(parents=True)

    (tmp_path / "README.md").write_text("# Session README\n", encoding="utf-8")
    (tmp_path / "turn_only.py").write_text("# Turn only\n", encoding="utf-8")
    (tmp_path / "extra.py").write_text("# Explicit extra\n", encoding="utf-8")

    (turn_dir / "meta.yaml").write_text("agent: developer\n", encoding="utf-8")
    (turn_dir / "turn.context").write_text("turn_only.py\n", encoding="utf-8")
    (session_root / "session.context").write_text("README.md\n", encoding="utf-8")
    return turn_dir


def _seed_explicit_workspace(tmp_path: Path) -> None:
    """Seeds the default set plus assets for manifest, directory, and missing cases."""
    _seed_context_workspace(tmp_path)
    (tmp_path / "manifest_only.py").write_text("# Manifest only\n", encoding="utf-8")
    (tmp_path / "review.context").write_text("manifest_only.py\n", encoding="utf-8")
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "guide.md").write_text("# Guide\n", encoding="utf-8")


def test_context_command_merges_explicit_file_inside_session(
    tmp_path: Path, monkeypatch
) -> None:
    """Inside a session the explicit path joins the Turn and Session scopes."""
    turn_dir = _seed_session_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["-c", "extra.py"], cwd=turn_dir)

    assert result.exit_code == 0, result.stdout
    assert "### [README.md](/README.md)" in result.stdout
    assert "### [turn_only.py](/turn_only.py)" in result.stdout
    assert "### [extra.py](/extra.py)" in result.stdout


def test_context_only_flag_excludes_default_context_set(
    tmp_path: Path, monkeypatch
) -> None:
    """--only exports the explicit path alone, dropping the init.context entries."""
    _seed_context_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["--only", "-c", "extra.py"])

    assert result.exit_code == 0, result.stdout
    assert "### [extra.py](/extra.py)" in result.stdout
    assert "### [README.md](/README.md)" not in result.stdout


def test_context_only_without_context_value_is_usage_error(
    tmp_path: Path, monkeypatch
) -> None:
    """--only without -c exits with a usage error before any context work."""
    _seed_context_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["--only"])

    assert result.exit_code == 2, result.stdout
    assert "## Resource Contents" not in result.stdout


def test_context_command_expands_context_manifest(tmp_path: Path, monkeypatch) -> None:
    """A .context value expands to the paths listed inside it."""
    _seed_explicit_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["-c", "review.context"])

    assert result.exit_code == 0, result.stdout
    assert "### [manifest_only.py](/manifest_only.py)" in result.stdout
    assert "### [review.context](/review.context)" not in result.stdout


def test_context_command_expands_directory(tmp_path: Path, monkeypatch) -> None:
    """A directory value expands to every file under it."""
    _seed_explicit_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["-c", "docs"])

    assert result.exit_code == 0, result.stdout
    assert "### [docs/guide.md](/docs/guide.md)" in result.stdout


def test_context_command_reports_missing_path(tmp_path: Path, monkeypatch) -> None:
    """A missing explicit path renders the FILE NOT FOUND marker."""
    _seed_explicit_workspace(tmp_path)

    result = _run_context(monkeypatch, tmp_path, ["-c", "missing.py"])

    assert result.exit_code == 0, result.stdout
    assert "### [missing.py](/missing.py)" in result.stdout
    assert "--- FILE NOT FOUND ---" in result.stdout
