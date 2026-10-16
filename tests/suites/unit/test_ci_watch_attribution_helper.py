"""Unit tests for the throwaway ci-watch attribution helper (POSIX ``sh``).

The helper at ``spikes/ci-watch-attribution/attribution.sh`` carries the
corrected attribution decision under development. It is validated here, then
baked inline into the shipped ``make ci-watch`` target and removed. Each
subcommand maps to one edge-case group: the subset verdict, the blocking
conclusion set, and the ancestor base resolution.

The helper is POSIX ``sh`` because the Make recipe runs under ``sh`` (``dash``
on Linux). ``resolve-base`` shells out to ``git`` and ``gh``; its tests reuse the
repository's fake ``gh`` harness and a throwaway git repository.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

from tests.harness.setup.ci_watch_fake_gh import CiWatchScenario, RunResult

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_HELPER = _PROJECT_ROOT / "spikes" / "ci-watch-attribution" / "attribution.sh"

# The helper is POSIX `sh`: it is invoked as `/bin/sh <helper> ...`. Windows has
# no `/bin/sh`, and the shipped target runs under `sh` on POSIX hosts only, so
# these tests are skipped on Windows via the repository's sanctioned guard idiom.
_posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="The attribution helper is a POSIX sh script.",
)


def _run_helper(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/sh", str(_HELPER), *args],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    ("new", "old", "expected"),
    [
        # Equal sets: nothing new failed.
        ("Test Suite,Quality Checks", "Test Suite,Quality Checks", "pre-existing"),
        # Strict subset (improvement): a pre-existing failure was partly cleared.
        ("Test Suite", "Test Suite,Quality Checks", "pre-existing"),
        # Empty new set: nothing new failed.
        ("", "Test Suite", "pre-existing"),
        # Both empty.
        ("", "", "pre-existing"),
        # Superset (regression): a new gate turned red.
        ("Test Suite,Quality Checks", "Test Suite", "regression"),
        # Disjoint (regression).
        ("Quality Checks", "Test Suite", "regression"),
        # Green base, failing new (regression).
        ("Test Suite", "", "regression"),
    ],
)
@_posix_only
def test_subset_verdict(new: str, old: str, expected: str) -> None:
    result = _run_helper("subset-verdict", new, old)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected, result.stdout


@pytest.mark.parametrize(
    ("conclusion", "expected"),
    [
        ("success", "pass"),
        ("failure", "attribute"),
        ("timed_out", "block"),
        ("cancelled", "block"),
        ("startup_failure", "block"),
        ("", "block"),
    ],
)
@_posix_only
def test_classify_conclusion(conclusion: str, expected: str) -> None:
    result = _run_helper("classify-conclusion", conclusion)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected, result.stdout


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
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
        text=True,
    ).stdout.strip()


def _run_helper_in(
    repo: Path, scenario_dir: Path, *args: str
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(scenario_dir / "bin"), env.get("PATH", "")])
    env["FAKE_GH_SCENARIO"] = str(scenario_dir)
    env["FAKE_GH_LOG"] = str(repo / "gh-invocations.log")
    return subprocess.run(
        ["/bin/sh", str(_HELPER), *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def git_repo() -> Iterator[Path]:
    """A throwaway git repo with three empty commits (root, middle, tip)."""
    repo = Path(tempfile.mkdtemp(prefix="teddy-attr-helper-"))
    try:
        _git(repo, "init", "-q")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "a")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "b")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "c")
        yield repo
    finally:
        shutil.rmtree(repo, ignore_errors=True)


@_posix_only
def test_resolve_base_returns_most_recent_ancestor_with_a_run(
    git_repo: Path,
) -> None:
    tip = _git(git_repo, "rev-parse", "HEAD")
    middle = _git(git_repo, "rev-parse", "HEAD~1")
    root = _git(git_repo, "rev-parse", "HEAD~2")
    scenario_dir = git_repo / "scenario"
    CiWatchScenario(
        runs=(
            RunResult(
                database_id=2, workflow="CI", head_sha=middle, conclusion="success"
            ),
            RunResult(
                database_id=1, workflow="CI", head_sha=root, conclusion="success"
            ),
        )
    ).write(scenario_dir)

    result = _run_helper_in(git_repo, scenario_dir, "resolve-base", tip, "CI")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == middle, result.stdout


@_posix_only
def test_resolve_base_falls_back_to_an_older_ancestor(git_repo: Path) -> None:
    tip = _git(git_repo, "rev-parse", "HEAD")
    root = _git(git_repo, "rev-parse", "HEAD~2")
    scenario_dir = git_repo / "scenario"
    CiWatchScenario(
        runs=(
            RunResult(
                database_id=1, workflow="CI", head_sha=root, conclusion="success"
            ),
        )
    ).write(scenario_dir)

    result = _run_helper_in(git_repo, scenario_dir, "resolve-base", tip, "CI")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == root, result.stdout


@_posix_only
def test_resolve_base_is_empty_when_no_ancestor_has_a_run(git_repo: Path) -> None:
    tip = _git(git_repo, "rev-parse", "HEAD")
    scenario_dir = git_repo / "scenario"
    CiWatchScenario(runs=()).write(scenario_dir)

    result = _run_helper_in(git_repo, scenario_dir, "resolve-base", tip, "CI")

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", result.stdout
