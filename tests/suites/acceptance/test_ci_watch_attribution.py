"""Acceptance: the shipped ``make ci-watch`` target drives ``gh`` end to end.

This is the wiring tracer bullet for the CI-watch attribution slice. It runs the
REAL ``make ci-watch`` recipe (the shipped bytes) inside a throwaway git
repository with a fake ``gh`` prepended to ``PATH``. The fake ``gh`` serves a
synthetic scenario, so the target must reach the fake binary, resolve the run,
and emit a per-workflow verdict. A passing test proves end-to-end connectivity;
behavioural attribution assertions are added by the slice's migration step.
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

from tests.harness.setup.ci_watch_fake_gh import (
    CiWatchScenario,
    JobResult,
    RunResult,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _PROJECT_ROOT / "Makefile"

# A portable fake `gh` binary is infeasible on Windows: `subprocess` resolves
# executables through CreateProcess, which never finds a `.sh` shim. The
# attribution logic is platform-independent, so this POSIX-only shadow test is
# skipped on Windows via the repository's sanctioned guard idiom.
_posix_only = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Fake `gh` shadow on PATH requires a POSIX executable.",
)


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


def _run_ci_watch(
    repo: Path, scenario_dir: Path, invocation_log: Path
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(scenario_dir / "bin"), env.get("PATH", "")])
    env["FAKE_GH_SCENARIO"] = str(scenario_dir)
    env["FAKE_GH_LOG"] = str(invocation_log)
    return subprocess.run(
        ["make", "ci-watch", "RETRY_POLLS=1", "RETRY_SLEEP=0"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def ci_repo() -> Iterator[Path]:
    """A throwaway git repo carrying the shipped Makefile and a CI workflow."""
    repo = Path(tempfile.mkdtemp(prefix="teddy-ci-watch-"))
    try:
        _git(repo, "init", "-q")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "one")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "two")
        _git(repo, "commit", "--allow-empty", "-q", "-m", "three")
        workflows = repo / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\n", encoding="utf-8")
        shutil.copy(_MAKEFILE, repo / "Makefile")
        yield repo
    finally:
        shutil.rmtree(repo, ignore_errors=True)


@_posix_only
def test_shipped_target_reaches_gh_and_emits_a_verdict(ci_repo: Path) -> None:
    tip_sha = _git(ci_repo, "rev-parse", "HEAD")
    base_sha = _git(ci_repo, "rev-parse", "HEAD~1")

    scenario_dir = ci_repo / "scenario"
    invocation_log = ci_repo / "gh-invocations.log"

    CiWatchScenario(
        runs=(
            RunResult(
                database_id=222,
                workflow="CI",
                head_sha=tip_sha,
                conclusion="failure",
                jobs=(
                    JobResult(
                        "Test Suite",
                        "failure",
                        steps=(("Run tests", "failure"),),
                    ),
                    JobResult("Quality Checks", "success"),
                ),
                log="CI\tRun tests\tboom\n",
            ),
            RunResult(
                database_id=111,
                workflow="CI",
                head_sha=base_sha,
                conclusion="success",
                jobs=(
                    JobResult("Test Suite", "success"),
                    JobResult("Quality Checks", "success"),
                ),
            ),
        )
    ).write(scenario_dir)

    result = _run_ci_watch(ci_repo, scenario_dir, invocation_log)

    # The shipped target reached the fake gh: end-to-end connectivity holds.
    assert invocation_log.read_text(encoding="utf-8").strip(), result.stderr
    # It resolved the run and emitted a per-workflow verdict, blocking the
    # synthetic regression. GNU Make reports any failed recipe as exit code 2,
    # so a blocking verdict surfaces here as a non-zero status.
    assert "CI:" in result.stdout, result.stdout
    assert result.returncode != 0, result.stdout


@_posix_only
def test_improvement_subset_is_attributed_pre_existing(ci_repo: Path) -> None:
    """A push that clears part of a pre-existing failure is not a regression."""
    tip_sha = _git(ci_repo, "rev-parse", "HEAD")
    base_sha = _git(ci_repo, "rev-parse", "HEAD~1")
    scenario_dir = ci_repo / "scenario"
    invocation_log = ci_repo / "gh-invocations.log"

    CiWatchScenario(
        runs=(
            RunResult(
                database_id=222,
                workflow="CI",
                head_sha=tip_sha,
                conclusion="failure",
                jobs=(
                    JobResult(
                        "Test Suite",
                        "failure",
                        steps=(("Run tests", "failure"),),
                    ),
                ),
            ),
            RunResult(
                database_id=111,
                workflow="CI",
                head_sha=base_sha,
                conclusion="failure",
                jobs=(
                    JobResult("Test Suite", "failure"),
                    JobResult("Quality Checks", "failure"),
                ),
            ),
        )
    ).write(scenario_dir)

    result = _run_ci_watch(ci_repo, scenario_dir, invocation_log)

    assert result.returncode == 0, result.stdout
    assert "pre-existing" in result.stdout, result.stdout


@_posix_only
def test_regression_superset_blocks_the_session(ci_repo: Path) -> None:
    """A push that turns a new blocking gate red is the developer's regression."""
    tip_sha = _git(ci_repo, "rev-parse", "HEAD")
    base_sha = _git(ci_repo, "rev-parse", "HEAD~1")
    scenario_dir = ci_repo / "scenario"
    invocation_log = ci_repo / "gh-invocations.log"

    CiWatchScenario(
        runs=(
            RunResult(
                database_id=222,
                workflow="CI",
                head_sha=tip_sha,
                conclusion="failure",
                jobs=(
                    JobResult(
                        "Test Suite",
                        "failure",
                        steps=(("Run tests", "failure"),),
                    ),
                    JobResult("Quality Checks", "failure"),
                ),
            ),
            RunResult(
                database_id=111,
                workflow="CI",
                head_sha=base_sha,
                conclusion="success",
                jobs=(
                    JobResult("Test Suite", "success"),
                    JobResult("Quality Checks", "success"),
                ),
            ),
        )
    ).write(scenario_dir)

    result = _run_ci_watch(ci_repo, scenario_dir, invocation_log)

    assert result.returncode != 0, result.stdout
    assert "regression" in result.stdout, result.stdout


@_posix_only
def test_multi_commit_push_resolves_the_run_bearing_ancestor(ci_repo: Path) -> None:
    """On a multi-commit push the base is the newest ancestor that has a run."""
    tip_sha = _git(ci_repo, "rev-parse", "HEAD")
    root_sha = _git(ci_repo, "rev-parse", "HEAD~2")
    scenario_dir = ci_repo / "scenario"
    invocation_log = ci_repo / "gh-invocations.log"

    # Only the tip and the root carry runs; HEAD~1 has none. A hardcoded
    # HEAD~1 base would fail safe against an absent run and falsely block.
    CiWatchScenario(
        runs=(
            RunResult(
                database_id=222,
                workflow="CI",
                head_sha=tip_sha,
                conclusion="failure",
                jobs=(
                    JobResult(
                        "Test Suite",
                        "failure",
                        steps=(("Run tests", "failure"),),
                    ),
                ),
            ),
            RunResult(
                database_id=111,
                workflow="CI",
                head_sha=root_sha,
                conclusion="failure",
                jobs=(JobResult("Test Suite", "failure"),),
            ),
        )
    ).write(scenario_dir)

    result = _run_ci_watch(ci_repo, scenario_dir, invocation_log)

    assert result.returncode == 0, result.stdout
    assert "pre-existing" in result.stdout, result.stdout
