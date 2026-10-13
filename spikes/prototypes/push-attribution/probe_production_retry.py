"""Production-driving probe for slice 00-36, deliverable Logic-3 (registration lag).

Drives the REAL production Makefile's `push:` target inside a throwaway git repo
that HAS workflow files under `.github/workflows/` (REAL `git`), with a fake `gh`
shim on PATH that models CI run-registration LAG for the pushed SHA.

Red (before the Logic-3 fix): the recipe performs a SINGLE discovery call, so
under lag it finds no workflow, runs no attribution, and exits 0 - silently
missing a real regression. The probe's discriminating assertions fail.
Green (after the Logic-3 fix): the bounded retry polls until the run registers
(reporting "after N poll(s)") and, when the run never registers, fail-safe blocks.

Usage:
    uv run python spikes/prototypes/push-attribution/probe_production_retry.py
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

NEVER = 10**9  # astronomical poll count => the run never registers

SCENARIOS = {
    "lag-red": {"base": [], "new": ["tests"], "lag_polls": 2},
    "never": {"base": [], "new": ["tests"], "lag_polls": NEVER},
}


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


def _setup(root, name, base_fail, new_fail):
    origin = root / f"{name}-origin.git"
    work = root / f"{name}-work"
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

    gh_state = root / f"{name}-gh.json"
    gh_state.write_text(
        json.dumps(
            {
                base: {
                    "workflows": {
                        "CI": {"run_id": "base-run", "failures": base_fail}
                    }
                },
                new: {
                    "workflows": {
                        "CI": {"run_id": "new-run", "failures": new_fail}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    fake_bin = root / f"{name}-fake-bin"
    fake_bin.mkdir()
    shim = fake_bin / "gh"
    shim.write_text(
        "#!/bin/sh\n" f'exec "{sys.executable}" "{FAKE_GH}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return work, fake_bin, gh_state, base, new


def _run_recipe(work, fake_bin, gh_state, lag_sha, lag_polls, lag_file):
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
    env["FAKE_GH_STATE"] = str(gh_state)
    env["FAKE_GH_LAG_SHA"] = lag_sha
    env["FAKE_GH_LAG_POLLS"] = str(lag_polls)
    env["FAKE_GH_LAG_FILE"] = str(lag_file)
    return _run(
        [
            "make", "-C", str(work), "-f", str(REPO_MAKEFILE), "push",
            "RETRY_SLEEP=0",
        ],
        cwd=work,
        env=env,
        check=False,
    )


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="teddy-push-prod-retry-"))
    results = {}
    try:
        for scenario, io in SCENARIOS.items():
            work, fake_bin, gh_state, base, new = _setup(
                root, scenario, io["base"], io["new"]
            )
            lag_file = root / f"{scenario}-lag.count"
            res = _run_recipe(
                work, fake_bin, gh_state, new, io["lag_polls"], lag_file
            )
            results[scenario] = {
                "rc": res.returncode,
                "out": res.stdout,
                "err": res.stderr,
                "base": base,
                "new": new,
            }

        print("=" * 72)
        print(
            f"PRODUCTION TARGET: {REPO_MAKEFILE} -> make push "
            "(registration lag)"
        )
        print("=" * 72)
        for scenario, r in results.items():
            print(f"### {scenario}")
            print(f"    base={r['base'][:8]} new={r['new'][:8]}")
            body = r["out"].rstrip() or "(no stdout)"
            for line in body.splitlines():
                print("    " + line)
            if r["err"].strip():
                print("    [stderr]")
                for line in r["err"].rstrip().splitlines():
                    print("    " + line)
            print(f"    --> exit={r['rc']}\n")

        lag_red = results["lag-red"]
        never = results["never"]

        checks = [
            (
                "lag-red: retried by polling (registered after 2 polls)",
                "after 2 poll(s)" in lag_red["out"],
            ),
            (
                "lag-red: base is the pre-push tip",
                f"base {lag_red['base']}" in lag_red["out"],
            ),
            (
                "lag-red: regression reported as YOUR regression (blocks)",
                lag_red["rc"] != 0 and "YOUR regression" in lag_red["out"],
            ),
            (
                "never: bounded fail-safe block after the poll budget",
                never["rc"] != 0
                and "fail-safe" in never["out"]
                and "after 10 poll(s)" in never["out"],
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