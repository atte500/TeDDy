"""Acceptance test for the post-commit hook's automated-git-operation guard.

Runs the REAL ``.githooks/post-commit.py`` script as a subprocess inside a
throwaway git repository. A fake ``uv`` (which exits 1) is PREPENDED to ``PATH``
so it shadows the real ``uv`` regardless of where the real one lives, while the
inherited ``PATH`` keeps ``git`` resolvable (the guard itself shells out to
``git rev-parse --git-dir``). The hook therefore has only two ways out: it
short-circuits at the guard (exit 0), or it falls through to the ``uv``
pre-flight, which fails (exit non-zero).

This is the end-to-end behavioural gate for the guard: with an automated git
operation in progress the hook MUST skip the suite, and with none in progress it
MUST NOT over-trigger and MUST run its normal pre-flight.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

_HOOK_PATH = Path(__file__).resolve().parents[3] / ".githooks" / "post-commit.py"

# A portable fake `uv` binary is infeasible: on Windows `subprocess` resolves
# executables through CreateProcess, which only appends `.exe` (a `.bat`/`.cmd`
# shim is never found). The guard logic is platform-independent and already
# covered cross-platform by the D1 unit test, so this POSIX-only shadow test is
# skipped on Windows via the repository's sanctioned guard idiom.
_posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Fake `uv` shadow on PATH requires a POSIX executable.",
)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _invoke_hook(repo: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(repo / "fake-bin"), env.get("PATH", "")])
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def hook_repo() -> Iterator[Path]:
    """A throwaway git repo with a fake `uv` (exit 1) shadowing the real one."""
    repo = Path(tempfile.mkdtemp(prefix="teddy-postcommit-"))
    bin_dir = repo / "fake-bin"
    bin_dir.mkdir()
    fake_uv = bin_dir / "uv"
    fake_uv.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    fake_uv.chmod(0o755)
    try:
        _git(repo, "init", "-q")
        # Two commits so _fail's `git reset --soft HEAD~1` resolves and the hook
        # exits cleanly rather than via an unhandled exception.
        _git(repo, "commit", "--allow-empty", "-q", "-m", "one")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "two")
        yield repo
    finally:
        shutil.rmtree(repo, ignore_errors=True)


@_posix_only
def test_rebase_in_progress_skips_the_suite(hook_repo: Path) -> None:
    (hook_repo / ".git" / "rebase-merge").touch()

    result = _invoke_hook(hook_repo)

    assert result.returncode == 0, result.stderr


@_posix_only
def test_no_git_operation_runs_the_preflight(hook_repo: Path) -> None:
    result = _invoke_hook(hook_repo)

    assert result.returncode != 0
