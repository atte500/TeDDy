"""Unit tests for the start-only workspace pull failure matrix.

``_pull_workspace_on_start`` must leave the workspace untouched and stay
silent on every precondition it cannot satisfy. It warns once when a risky or
failed pull leaves the workspace unchanged, and it reports a successful
fast-forward. The Git process is injected through the ``run_func`` seam so
each decision is deterministic without spawning a real repository.
"""

import subprocess

import pytest

from teddy_executor.adapters.inbound.session_cli_handlers import (
    _pull_workspace_on_start,
)

FAST_FORWARD_PREFIX = "Workspace fast-forwarded"
SKIPPED_WARNING = "⚠ Workspace pull skipped; continuing with the current branch."
TIMEOUT_WARNING = "⚠ Workspace pull timed out; continuing without it."


class FakeGitRunner:
    """Stateful Git process double covering the pull decision table.

    The double answers the read-only probes with canned results and models the
    pull by advancing ``HEAD`` only when the pull succeeds with a fast-forward.
    Every invocation is recorded so tests can prove which steps ran.
    """

    def __init__(
        self,
        *,
        symbolic_ref_ok: bool = True,
        upstream_ok: bool = True,
        status_output: str = "",
        pull_returncode: int = 0,
        fast_forward_count: int = 1,
    ) -> None:
        self.symbolic_ref_ok = symbolic_ref_ok
        self.upstream_ok = upstream_ok
        self.status_output = status_output
        self.pull_returncode = pull_returncode
        self.fast_forward_count = fast_forward_count
        self.head = "before"
        self.calls: list[list[str]] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        operation = cmd[1]
        if operation == "symbolic-ref":
            returncode = 0 if self.symbolic_ref_ok else 1
            stdout = ""
        elif operation == "rev-parse":
            if "@{u}" in cmd:
                returncode = 0 if self.upstream_ok else 1
                stdout = "origin/main\n"
            else:
                returncode = 0
                stdout = f"{self.head}\n"
        elif operation == "status":
            returncode = 0
            stdout = self.status_output
        elif operation == "pull":
            if self.pull_returncode == 0 and self.fast_forward_count:
                self.head = "after"
            returncode = self.pull_returncode
            stdout = ""
        elif operation == "rev-list":
            returncode = 0
            stdout = f"{self.fast_forward_count}\n"
        else:
            returncode = 1
            stdout = ""
        return self._completed(cmd, returncode, stdout)

    @staticmethod
    def _completed(cmd, returncode, stdout):
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    def operations(self) -> list[str]:
        return [call[1] for call in self.calls]


@pytest.fixture
def git_repository(tmp_path, monkeypatch):
    """A working directory that carries a ``.git`` marker."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_disabled_pull_skips_before_running_git(git_repository, mock_config, capsys):
    """A disabled ``workspace.pull`` toggle never invokes Git."""
    mock_config.get_setting.side_effect = lambda key, default=None: (
        False if key == "workspace.pull" else default
    )
    runner = FakeGitRunner()

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert runner.calls == []
    assert capsys.readouterr().err == ""


def test_missing_git_directory_skips_silently(
    tmp_path, monkeypatch, mock_config, capsys
):
    """A workspace that is not a repository stays silent without invoking Git."""
    monkeypatch.chdir(tmp_path)
    runner = FakeGitRunner()

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert runner.calls == []
    assert capsys.readouterr().err == ""


def test_detached_head_skips_silently(git_repository, mock_config, capsys):
    """A detached HEAD has no branch to fast-forward and stays silent."""
    runner = FakeGitRunner(symbolic_ref_ok=False)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == ""


def test_missing_upstream_skips_silently(git_repository, mock_config, capsys):
    """A branch without an upstream has nothing to pull and stays silent."""
    runner = FakeGitRunner(upstream_ok=False)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize(
    "marker", ["rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD"]
)
def test_in_progress_operation_skips_silently(
    git_repository, mock_config, capsys, marker
):
    """An in-progress Git operation is never interrupted by a pull."""
    (git_repository / ".git" / marker).touch()
    runner = FakeGitRunner()

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == ""


def test_tracked_changes_warn_and_skip_the_pull(git_repository, mock_config, capsys):
    """Tracked worktree changes warn once and skip the pull."""
    runner = FakeGitRunner(status_output=" M src/app.py\n")

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert SKIPPED_WARNING in capsys.readouterr().err


def test_untracked_files_do_not_block_a_fast_forward(
    git_repository, mock_config, capsys
):
    """Untracked files never block a fast-forward, which then reports its count."""
    runner = FakeGitRunner(status_output="?? scratch.txt\n", fast_forward_count=2)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" in runner.operations()
    assert f"{FAST_FORWARD_PREFIX} (2 commits)" in capsys.readouterr().err


def test_failed_pull_warns_and_continues(git_repository, mock_config, capsys):
    """A non-zero pull exit warns once and leaves the workspace unchanged."""
    runner = FakeGitRunner(pull_returncode=1)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert SKIPPED_WARNING in capsys.readouterr().err


def test_timeout_warns_and_continues(git_repository, mock_config, capsys):
    """A timed-out Git command warns once and lets the session proceed."""

    def timeout_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 15)

    _pull_workspace_on_start(mock_config, run_func=timeout_runner)

    assert TIMEOUT_WARNING in capsys.readouterr().err


def test_fast_forward_reports_the_commit_count(git_repository, mock_config, capsys):
    """A multi-commit fast-forward names the commit count in one line."""
    runner = FakeGitRunner(fast_forward_count=3)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert f"{FAST_FORWARD_PREFIX} (3 commits)" in capsys.readouterr().err


def test_single_commit_fast_forward_uses_the_singular_noun(
    git_repository, mock_config, capsys
):
    """A one-commit fast-forward uses the singular noun."""
    runner = FakeGitRunner(fast_forward_count=1)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert f"{FAST_FORWARD_PREFIX} (1 commit)" in capsys.readouterr().err


def test_already_current_workspace_stays_silent(git_repository, mock_config, capsys):
    """A successful pull that moves no commit stays silent."""
    runner = FakeGitRunner(fast_forward_count=0)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert capsys.readouterr().err == ""
