"""Production-driving probe for slice 00-36, deliverable Logic-1 (base capture).

Unlike probe.py / probe_retry.py (which compare inline recipe variants), this
probe drives the REAL production Makefile's `push:` target inside a throwaway
git repo (REAL `git`) with a fake `gh` shim prepended to PATH, and asserts that
the attribution base is captured BEFORE the push.

Red (before the Logic-1 fix): the pushed SHA advances origin/main, so BASE
collapses onto the pushed SHA -> the assertion fails.
Green (after the Logic-1 fix): BASE equals the pre-push remote tip -> passes.

Usage:
    uv run python spikes/prototypes/push-attribution/probe_production.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
REPO_MAKEFILE = SPIKE_DIR.parents[2] / "Makefile"
FAKE_GH = SPIKE_DIR / "fake_gh.py"


def _run(cmd, cwd, env=None, check=True):
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, check=check
    )


def _git(repo, *args, check=True):
    return _run(
        [
            "git",
            "-c", "user.email=probe@example.com",
            "-c", "user.name=Probe",
            "-c", "commit.gpgsign=false",
            "-c", "init.defaultBranch=main",
            *args,
        ],
        cwd=repo,
        check=check,
    )


def _setup(root):
    origin = root / "origin.git"
    work = root / "work"
    _run(["git", "init", "--bare", "-q", str(origin)], cwd=root)
    _run(["git", "init", "-q", str(work)], cwd=root)
    workflows = work / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "ci.yml").write_text("name: CI\non: push\n", encoding="utf-8")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "branch", "-M", "main")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    base = _git(work, "rev-parse", "HEAD").stdout.strip()
    _git(work, "commit", "--allow-empty", "-q", "-m", "change")
    new = _git(work, "rev-parse", "HEAD").stdout.strip()

    gh_state = root / "gh.json"
    gh_state.write_text(
        json.dumps(
            {
                base: {"workflows": {"CI": {"run_id": "base-run", "failures": []}}},
                new: {"workflows": {"CI": {"run_id": "new-run", "failures": []}}},
            }
        ),
        encoding="utf-8",
    )

    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    shim = fake_bin / "gh"
    shim.write_text(
        "#!/bin/sh\n" f'exec "{sys.executable}" "{FAKE_GH}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return work, fake_bin, gh_state, base, new


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-prod-"))
    try:
        work, fake_bin, gh_state, base, new = _setup(root)
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
        env["FAKE_GH_STATE"] = str(gh_state)

        res = _run(
            ["make", "-C", str(work), "-f", str(REPO_MAKEFILE), "push"],
            cwd=work,
            env=env,
            check=False,
        )

        print("=" * 72)
        print(f"PRODUCTION TARGET: {REPO_MAKEFILE} -> make push")
        print("=" * 72)
        print(f"    pre-push tip (base) = {base[:8]}")
        print(f"    pushed     (new)    = {new[:8]}")
        print(f"    exit = {res.returncode}")
        for line in (res.stdout.rstrip() or "(no stdout)").splitlines():
            print("    " + line)
        if res.stderr.strip():
            print("    [stderr]")
            for line in res.stderr.rstrip().splitlines():
                print("    " + line)

        checks = [
            (
                f"base captured BEFORE push (base == pre-push tip {base[:8]})",
                f"(base {base})" in res.stdout,
            ),
            (
                f"base did NOT collapse onto the pushed SHA ({new[:8]})",
                f"(base {new})" not in res.stdout,
            ),
        ]

        print("=" * 72)
        print("ASSERTIONS")
        print("=" * 72)
        ok = True
        for desc, passed in checks:
            print(f"  [{'PASS' if passed else 'FAIL'}] {desc}")
            ok = ok and passed
        print("=" * 72)
        print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
        return 0 if ok else 1
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())