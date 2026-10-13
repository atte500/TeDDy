"""Unit tests for the post-commit hook's automated-git-operation guard.

The post-commit test gate (``.githooks/post-commit.py``) must skip the full
suite while an automated git operation (rebase / merge / cherry-pick) is in
progress. During ``git pull --rebase`` git fires the ``post-commit`` hook
once per replayed commit; because the hook reverts on failure
(``git reset --soft HEAD~1``), a failing replay would silently drop that
commit while the rebase still reports success.

This module loads the hook as a standalone script (mirroring
``tests/suites/unit/test_githooks_posix_only_patches.py``) and drives
``_in_progress_git_operation()`` inside a real, throwaway git repository so
that ``git rev-parse --git-dir`` resolves deterministically.
"""

import importlib.util
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator

import pytest

_HOOK_PATH = Path(__file__).resolve().parents[3] / ".githooks" / "post-commit.py"

_MARKERS = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD")


def _load_hook() -> ModuleType:
    spec = importlib.util.spec_from_file_location("post_commit_hook", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def hook() -> Any:
    return _load_hook()


@pytest.fixture
def git_repo(monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A real, throwaway git repository used as the process CWD."""
    repo = Path(tempfile.mkdtemp())
    try:
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True, capture_output=True)
        monkeypatch.chdir(repo)
        yield repo
    finally:
        shutil.rmtree(repo, ignore_errors=True)


def test_returns_false_without_markers(hook: Any, git_repo: Path) -> None:
    assert hook._in_progress_git_operation() is False


@pytest.mark.parametrize("marker", _MARKERS)
def test_returns_true_for_each_marker(hook: Any, git_repo: Path, marker: str) -> None:
    (git_repo / ".git" / marker).touch()
    assert hook._in_progress_git_operation() is True
