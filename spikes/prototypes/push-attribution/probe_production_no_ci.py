"""Production-driving probe for slice 00-36, deliverable Logic-2 (no-CI case).

Drives the REAL production Makefile's `push:` target inside a throwaway git repo
that has NO workflow files under `.github/workflows/` (REAL `git`), with a fake
`gh` shim prepended to PATH that RECORDS every invocation.

Red (before the Logic-2 fix): the current recipe pushes, then proceeds into the
CI-discovery loop, so it does NOT log `No CI configured - skipping attribution`
and it DOES invoke `gh` -> two assertions fail.
Green (after the Logic-2 fix): the short-circuit fires BEFORE any `gh` call, so
the notice is logged, `gh` is never invoked, and the target exits 0.

Usage:
    uv run python spikes/prototypes/push-attribution/probe_production_no_ci.py
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
    # Deliberately NO .github/workflows/ directory: this repo has no CI.
    _git(work, "commit", "--allow-empty", "-q", "-m", "base")
    _git(work, "branch", "-M", "main")
    _git(work, "remote", "add", "origin", str(origin))
    _git(work, "push", "-u", "origin", "main")
    _git(work, "commit", "--allow-empty", "-q", "-m", "change")

    gh_state = root / "gh.json"
    gh_state.write_text(json.dumps({}), encoding="utf-8")

    marker = root / "gh-invocations.log"
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    shim = fake_bin / "gh"
    shim.write_text(
        "#!/bin/sh\n"
        'echo "$@" >> "$GH_MARKER"\n'
        f'exec "{sys.executable}" "{FAKE_GH}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return work, fake_bin, gh_state, marker


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-noci-"))
    try:
        work, fake_bin, gh_state, marker = _setup(root)
        env = dict(os.environ)
        env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
        env["FAKE_GH_STATE"] = str(gh_state)
        env["GH_MARKER"] = str(marker)

        res = _run(
            ["make", "-C", str(work), "-f", str(REPO_MAKEFILE), "push"],
            cwd=work,
            env=env,
            check=False,
        )

        invoked = marker.read_text(encoding="utf-8") if marker.exists() else ""
        invoked_lines = invoked.splitlines()

        print("=" * 72)
        print(
            f"PRODUCTION TARGET: {REPO_MAKEFILE} -> make push "
            "(repo WITHOUT CI)"
        )
        print("=" * 72)
        print(f"    exit = {res.returncode}")
        for line in (res.stdout.rstrip() or "(no stdout)").splitlines():
            print("    " + line)
        if res.stderr.strip():
            print("    [stderr]")
            for line in res.stderr.rstrip().splitlines():
                print("    " + line)
        print(f"    gh invocations = {invoked_lines or '(none)'}")

        checks = [
            ("exits 0 (non-blocking)", res.returncode == 0),
            (
                "logs 'No CI configured - skipping attribution'",
                "No CI configured - skipping attribution" in res.stdout,
            ),
            ("never invoked gh (true short-circuit)", invoked == ""),
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