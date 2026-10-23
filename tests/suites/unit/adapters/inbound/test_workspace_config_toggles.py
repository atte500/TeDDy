"""Unit tests for the start-only workspace pull failure matrix.

``_pull_workspace_on_start`` must leave the workspace untouched on every
precondition it cannot satisfy. Every skip and every failure warns exactly
once and names its cause, so the user can tell why the workspace stayed
unchanged. A skip therefore carries no checkmark. A successful pull reports
its outcome, including the up-to-date case. The Git process is injected
through the ``run_func`` seam so each decision is deterministic without
spawning a real repository.
"""

import subprocess

import pytest

from teddy_executor.adapters.inbound import session_cli_handlers
from teddy_executor.adapters.inbound.session_cli_handlers import (
    _pull_workspace_on_start,
    _run_health_checks,
)

FAST_FORWARD_PREFIX = "Workspace fast-forwarded"
DETACHED_HEAD_WARNING = "⚠ Workspace pull skipped: detached HEAD."
NO_UPSTREAM_WARNING = "⚠ Workspace pull skipped: no upstream branch."
IN_PROGRESS_WARNING = "⚠ Workspace pull skipped: Git operation in progress."
NOT_A_REPOSITORY_WARNING = "⚠ Workspace pull skipped: not a Git repository."
FAILED_WARNING = "⚠ Workspace pull failed."
TIMEOUT_WARNING = "⚠ Workspace pull timed out after 15s."
GIT_UNAVAILABLE_WARNING = "⚠ Workspace pull failed: git is unavailable."
UP_TO_DATE_NOTICE = "✓ Workspace up-to-date with remote"


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


def test_missing_git_directory_reports_not_a_repository(
    tmp_path, monkeypatch, mock_config, capsys
):
    """A workspace without a repository warns and never invokes Git."""
    monkeypatch.chdir(tmp_path)
    runner = FakeGitRunner()

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert runner.calls == []
    assert capsys.readouterr().err == NOT_A_REPOSITORY_WARNING + "\n"


def test_detached_head_names_its_reason(git_repository, mock_config, capsys):
    """A detached HEAD names the state and skips the pull."""
    runner = FakeGitRunner(symbolic_ref_ok=False)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == DETACHED_HEAD_WARNING + "\n"


def test_missing_upstream_names_its_reason(git_repository, mock_config, capsys):
    """A branch without an upstream names the state and skips the pull."""
    runner = FakeGitRunner(upstream_ok=False)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == NO_UPSTREAM_WARNING + "\n"


@pytest.mark.parametrize(
    "marker", ["rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD"]
)
def test_in_progress_operation_names_its_reason(
    git_repository, mock_config, capsys, marker
):
    """An in-progress Git operation is never interrupted and names the state."""
    (git_repository / ".git" / marker).touch()
    runner = FakeGitRunner()

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" not in runner.operations()
    assert capsys.readouterr().err == IN_PROGRESS_WARNING + "\n"


def test_tracked_changes_count_as_one_uncommitted_file(
    git_repository, mock_config, capsys
):
    """One tracked change warns once with the singular noun and skips the pull."""
    runner = FakeGitRunner(status_output=" M src/app.py\n")

    _pull_workspace_on_start(mock_config, run_func=runner)

    err = capsys.readouterr().err
    assert "pull" not in runner.operations()
    assert err == "⚠ Workspace pull skipped: 1 uncommitted file.\n"


def test_multiple_tracked_changes_report_the_plural_count(
    git_repository, mock_config, capsys
):
    """Two tracked changes warn once with the plural noun."""
    runner = FakeGitRunner(status_output=" M src/app.py\nMM tests/conftest.py\n")

    _pull_workspace_on_start(mock_config, run_func=runner)

    err = capsys.readouterr().err
    assert "pull" not in runner.operations()
    assert err == "⚠ Workspace pull skipped: 2 uncommitted files.\n"


def test_untracked_files_do_not_block_a_fast_forward(
    git_repository, mock_config, capsys
):
    """Untracked files never block a fast-forward, which then reports its count."""
    runner = FakeGitRunner(status_output="?? scratch.txt\n", fast_forward_count=2)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert "pull" in runner.operations()
    assert f"{FAST_FORWARD_PREFIX} (2 commits)" in capsys.readouterr().err


def test_failed_pull_reports_a_failure_not_a_skip(git_repository, mock_config, capsys):
    """A non-zero pull exit reports a failure and leaves the workspace unchanged."""
    runner = FakeGitRunner(pull_returncode=1)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert capsys.readouterr().err == FAILED_WARNING + "\n"


def test_timeout_names_the_configured_budget(git_repository, mock_config, capsys):
    """A timed-out Git command warns once and names the configured budget."""

    def timeout_runner(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 15)

    _pull_workspace_on_start(mock_config, run_func=timeout_runner)

    assert capsys.readouterr().err == TIMEOUT_WARNING + "\n"


def test_unavailable_git_binary_warns_and_continues(
    git_repository, mock_config, capsys
):
    """A missing git binary warns once instead of aborting session startup."""

    def missing_git_runner(cmd, **kwargs):
        raise FileNotFoundError("git")

    _pull_workspace_on_start(mock_config, run_func=missing_git_runner)

    err = capsys.readouterr().err
    assert err == GIT_UNAVAILABLE_WARNING + "\n"


def test_fast_forward_reports_the_commit_count(git_repository, mock_config, capsys):
    """A multi-commit fast-forward prints one checkmark line with no trailing blank."""
    runner = FakeGitRunner(fast_forward_count=3)

    _pull_workspace_on_start(mock_config, run_func=runner)

    err = capsys.readouterr().err
    assert err == f"✓ {FAST_FORWARD_PREFIX} (3 commits)\n"


def test_single_commit_fast_forward_uses_the_singular_noun(
    git_repository, mock_config, capsys
):
    """A one-commit fast-forward uses the singular noun."""
    runner = FakeGitRunner(fast_forward_count=1)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert f"{FAST_FORWARD_PREFIX} (1 commit)" in capsys.readouterr().err


def test_already_current_workspace_reports_up_to_date(
    git_repository, mock_config, capsys
):
    """A successful pull that moves no commit confirms the workspace is up to date."""
    runner = FakeGitRunner(fast_forward_count=0)

    _pull_workspace_on_start(mock_config, run_func=runner)

    assert capsys.readouterr().err == UP_TO_DATE_NOTICE + "\n"


def test_disabled_workspace_gates_skip_their_steps_silently(
    tmp_path, monkeypatch, mock_config, capsys
):
    """A disabled gate runs no step and prints no reminder about the opt-out."""
    monkeypatch.chdir(tmp_path)
    invoked: list[str] = []
    monkeypatch.setattr(
        session_cli_handlers, "_ensure_commit_hooks", lambda: invoked.append("hooks")
    )
    monkeypatch.setattr(
        session_cli_handlers, "_check_git_initialized", lambda: invoked.append("init")
    )
    mock_config.get_setting.side_effect = lambda key, default=None: (
        False if key in {"workspace.pre-commit", "workspace.init"} else default
    )

    _run_health_checks(mock_config)

    assert invoked == []
    assert capsys.readouterr().err == ""
