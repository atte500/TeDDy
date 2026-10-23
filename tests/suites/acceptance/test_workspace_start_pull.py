"""Acceptance coverage for the start-only workspace fast-forward pull.

The public ``teddy start`` entry point must fast-forward a branch that is
behind its upstream when ``workspace.pull`` is enabled.
"""

import os
import subprocess
from pathlib import Path

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


FAST_FORWARD_PREFIX = "Workspace fast-forwarded"


def _git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )


def _configure_identity(repo: Path) -> None:
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test"], repo)


def _seed_workspace_repository(repo: Path, origin: Path) -> None:
    _git(["init", "-b", "main"], repo)
    _configure_identity(repo)
    (repo / "README.md").write_text("# Workspace\n", encoding="utf-8")
    _git(["add", "."], repo)
    _git(["commit", "-m", "initial"], repo)
    _git(["remote", "add", "origin", str(origin)], repo)
    _git(["push", "-u", "origin", "main"], repo)


def _advance_origin(origin: Path, workdir: Path) -> None:
    clone = workdir / "clone"
    _git(["clone", str(origin), str(clone)], workdir)
    _configure_identity(clone)
    (clone / "CHANGELOG.md").write_text("new\n", encoding="utf-8")
    _git(["add", "."], clone)
    _git(["commit", "-m", "advance"], clone)
    _git(["push", "origin", "main"], clone)


# Real git subprocess work plus a full CLI start can outlast the shared CI
# budget under Windows contention, and a thread-method expiry kills the worker.
@pytest.mark.timeout(30)
def test_start_fast_forwards_a_behind_workspace(
    tmp_path: Path, tmp_path_factory, monkeypatch
) -> None:
    """A behind branch fast-forwards and the pulled file appears."""
    origin_root = tmp_path_factory.mktemp("origin")
    origin = origin_root / "origin.git"
    _git(["init", "--bare", "-b", "main", str(origin)], origin_root)

    TestEnvironment(monkeypatch, tmp_path).setup().with_real_config()

    _seed_workspace_repository(tmp_path, origin)
    _advance_origin(origin, tmp_path_factory.mktemp("advance"))

    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "config.yaml").write_text(
        "workspace:\n  init: false\n  pre-commit: false\n  pull: true\n",
        encoding="utf-8",
    )

    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_cli_command(
        ["start", "pull-session", "-a", "developer", "-m", "Test pull"],
        input="n\n",
    )

    output = result.stdout + result.stderr
    assert result.exit_code == 0, output
    assert FAST_FORWARD_PREFIX in output
    assert (tmp_path / "CHANGELOG.md").exists()
