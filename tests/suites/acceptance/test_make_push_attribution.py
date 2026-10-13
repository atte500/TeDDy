"""End-to-end acceptance gate for the `make push` CI attribution wiring.

Drives the REAL repository ``Makefile`` ``push:`` target END-TO-END inside a
throwaway git repository (REAL ``git``, REAL ``make``), with a fake ``gh`` shim
prepended to ``PATH`` that answers the recipe's exact query surface. This is the
committed behavioural gate for the slice's happy-path Gherkin scenarios:

* the attribution base is captured BEFORE the push (the pre-push remote tip),
  so a regression the push introduced is reported as YOUR regression;
* a repository with no CI configured short-circuits with a notice and exits 0;
* a NON-BLOCKING job failure (the RUN conclusion stays ``success``) is reported
  as a triage item and does NOT block; and
* a JOB-LESS base run (an invalid-workflow failure with zero jobs) is NOT read
  as green and fails safe.

POSIX-only: ``make`` and a ``/bin/sh``-executable shim host do not exist on
Windows CI, so this test is skipped there (mirroring the sanctioned
``sys.platform == "win32"`` guard idiom), keeping the OS test matrix green. The
probes under ``spikes/prototypes/push-attribution/`` remain the primary POSIX
verification and the Red/Green evidence for the underlying deliverables.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_MAKEFILE = _REPO_ROOT / "Makefile"

_posix_only = pytest.mark.skipif(
    sys.platform == "win32"
    or shutil.which("make") is None
    or shutil.which("git") is None,
    reason="Driving the real Makefile push target requires make, git, and a POSIX shim host.",
)

# Minimal stand-in for the GitHub CLI surface the `push:` recipe queries. Reads
# its state from $FAKE_GH_STATE:
#   {"<sha>": {"<workflow>": {"run_id": ..., "conclusion": ...,
#                             "jobs": [{"name": ..., "conclusion": ...}]}}}
_FAKE_GH_IMPL = """\
import json
import os
import sys


def _load():
    path = os.environ.get("FAKE_GH_STATE")
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _find_run(data, run_id):
    for runs in data.values():
        for entry in runs.values():
            if str(entry.get("run_id")) == str(run_id):
                return entry
    return None


def main(argv):
    data = _load()
    args = argv[1:]
    if args[:2] == ["run", "list"]:
        sha = workflow = None
        index = 2
        while index < len(args):
            if args[index] == "--commit" and index + 1 < len(args):
                sha = args[index + 1]
                index += 2
            elif args[index] == "--workflow" and index + 1 < len(args):
                workflow = args[index + 1]
                index += 2
            else:
                index += 1
        runs = data.get(sha, {})
        if workflow is None:
            for name in sorted(runs):
                print(name)
        elif workflow in runs:
            print(runs[workflow]["run_id"])
        return 0
    if args[:2] == ["run", "view"]:
        run_id = args[2] if len(args) > 2 else None
        entry = _find_run(data, run_id)
        if entry is None:
            return 1
        if "--log-failed" in args:
            sys.stdout.write(entry.get("failed_log", ""))
            return 0
        json_fields = ""
        jq = ""
        index = 3
        while index < len(args):
            if args[index] == "--json" and index + 1 < len(args):
                json_fields = args[index + 1]
                index += 2
            elif args[index] == "--jq" and index + 1 < len(args):
                jq = args[index + 1]
                index += 2
            else:
                index += 1
        if json_fields == "conclusion":
            print(entry.get("conclusion", ""))
            return 0
        if json_fields == "jobs":
            jobs = entry.get("jobs", [])
            if "steps" in jq:
                failures = sorted(
                    step["name"]
                    for job in jobs
                    for step in job.get("steps", [])
                    if step.get("conclusion") == "failure"
                )
                print(", ".join(failures))
            elif "length" in jq:
                print(len(jobs))
            else:
                failures = sorted(
                    job["name"] for job in jobs if job.get("conclusion") == "failure"
                )
                print(",".join(failures))
            return 0
        return 0
    if args[:2] == ["run", "watch"]:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "init.defaultBranch=main",
            *args,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _make_repo(root: Path, name: str, *, with_ci: bool):
    origin = root / f"{name}-origin.git"
    work = root / f"{name}-work"
    subprocess.run(
        ["git", "init", "--bare", "-q", str(origin)], check=True, capture_output=True
    )
    subprocess.run(["git", "init", "-q", str(work)], check=True, capture_output=True)
    if with_ci:
        workflows = work / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").write_text("name: CI\non: push\n", encoding="utf-8")
        _git(work, "add", "-A")
    _git(work, "commit", "--allow-empty", "-q", "-m", "base")
    _git(work, "branch", "-M", "main")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    base = _git(work, "rev-parse", "HEAD").stdout.strip()
    _git(work, "commit", "--allow-empty", "-q", "-m", "change")
    new = _git(work, "rev-parse", "HEAD").stdout.strip()
    return work, base, new


def _make_fake_gh(root: Path, name: str, state: dict):
    bin_dir = root / f"{name}-bin"
    bin_dir.mkdir()
    impl = bin_dir / "fake_gh.py"
    impl.write_text(_FAKE_GH_IMPL, encoding="utf-8")
    state_file = root / f"{name}-gh-state.json"
    state_file.write_text(json.dumps(state), encoding="utf-8")
    shim = bin_dir / "gh"
    shim.write_text(
        "#!/bin/sh\n"
        'echo "$@" >> "${GH_MARKER:-/dev/null}"\n'
        f'exec "{sys.executable}" "{impl}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return bin_dir, state_file


def _run_push(
    work: Path, bin_dir: Path, state_file: Path, *, marker: Path | None = None
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(bin_dir), env.get("PATH", "")])
    env["FAKE_GH_STATE"] = str(state_file)
    if marker is not None:
        env["GH_MARKER"] = str(marker)
    return subprocess.run(
        ["make", "-C", str(work), "-f", str(_MAKEFILE), "push", "RETRY_SLEEP=0"],
        cwd=work,
        env=env,
        capture_output=True,
        text=True,
    )


@_posix_only
def test_make_push_captures_pre_push_base_and_blocks_a_regression() -> None:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-wiring-"))
    try:
        work, base, new = _make_repo(root, "ci", with_ci=True)
        bin_dir, state_file = _make_fake_gh(
            root,
            "ci",
            {
                base: {
                    "CI": {
                        "run_id": "base-run",
                        "conclusion": "success",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "success",
                            }
                        ],
                    }
                },
                new: {
                    "CI": {
                        "run_id": "new-run",
                        "conclusion": "failure",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "failure",
                            }
                        ],
                    }
                },
            },
        )

        result = _run_push(work, bin_dir, state_file)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "YOUR regression" in result.stdout
        assert f"(base {base})" in result.stdout
        assert f"(base {new})" not in result.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


@_posix_only
def test_make_push_skips_attribution_when_no_ci_configured() -> None:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-wiring-"))
    try:
        work, _base, _new = _make_repo(root, "noci", with_ci=False)
        bin_dir, state_file = _make_fake_gh(root, "noci", {})
        marker = root / "gh-invocations.log"

        result = _run_push(work, bin_dir, state_file, marker=marker)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "No CI configured - skipping attribution" in result.stdout
        assert not marker.exists() or marker.read_text(encoding="utf-8") == ""
    finally:
        shutil.rmtree(root, ignore_errors=True)


@_posix_only
def test_make_push_does_not_block_on_a_non_blocking_job_failure() -> None:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-wiring-"))
    try:
        work, base, new = _make_repo(root, "nonblocking", with_ci=True)
        bin_dir, state_file = _make_fake_gh(
            root,
            "nonblocking",
            {
                base: {
                    "CI": {
                        "run_id": "base-run",
                        "conclusion": "success",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "success",
                            }
                        ],
                    }
                },
                new: {
                    "CI": {
                        "run_id": "new-run",
                        "conclusion": "success",
                        "failed_log": (
                            "Quality Checks\tRun Pre-commit Hooks (fast: formatters, secrets)\t"
                            "2026-10-13T00:00:00.0000000Z Error: detect-secrets flagged 2 potential secrets\n"
                            "Quality Checks\tRun Pre-commit Hooks (fast: formatters, secrets)\t"
                            "2026-10-13T00:00:01.0000000Z Error: ruff-lint found 104 errors\n"
                        ),
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "success",
                            },
                            {
                                "name": "Quality Checks",
                                "conclusion": "failure",
                                "steps": [
                                    {
                                        "name": "Run Pre-commit Hooks (fast: formatters, secrets)",
                                        "conclusion": "failure",
                                    }
                                ],
                            },
                        ],
                    }
                },
            },
        )

        result = _run_push(work, bin_dir, state_file)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "YOUR regression" not in result.stdout
        assert "Quality Checks" in result.stdout
        assert "Run Pre-commit Hooks (fast: formatters, secrets)" in result.stdout
        assert "detect-secrets flagged 2 potential secrets" in result.stdout
        assert "make logs new-run" in result.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


@_posix_only
def test_make_push_does_not_treat_a_job_less_base_as_green() -> None:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-wiring-"))
    try:
        work, base, new = _make_repo(root, "jobless", with_ci=True)
        bin_dir, state_file = _make_fake_gh(
            root,
            "jobless",
            {
                base: {
                    "CI": {
                        "run_id": "base-run",
                        "conclusion": "failure",
                        "jobs": [],
                    }
                },
                new: {
                    "CI": {
                        "run_id": "new-run",
                        "conclusion": "failure",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "failure",
                            }
                        ],
                    }
                },
            },
        )

        result = _run_push(work, bin_dir, state_file)

        assert result.returncode != 0, result.stdout + result.stderr
        assert "YOUR regression" in result.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)


@_posix_only
def test_make_push_reports_a_pre_existing_failure_without_blocking() -> None:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-wiring-"))
    try:
        work, base, new = _make_repo(root, "preexisting", with_ci=True)
        bin_dir, state_file = _make_fake_gh(
            root,
            "preexisting",
            {
                base: {
                    "CI": {
                        "run_id": "base-run",
                        "conclusion": "failure",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "failure",
                            }
                        ],
                    }
                },
                new: {
                    "CI": {
                        "run_id": "new-run",
                        "conclusion": "failure",
                        "jobs": [
                            {
                                "name": "Test Suite (ubuntu-latest)",
                                "conclusion": "failure",
                            }
                        ],
                    }
                },
            },
        )

        result = _run_push(work, bin_dir, state_file)

        assert result.returncode == 0, result.stdout + result.stderr
        assert "pre-existing" in result.stdout
    finally:
        shutil.rmtree(root, ignore_errors=True)
