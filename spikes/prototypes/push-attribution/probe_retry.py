"""Focused sub-probe for slice 00-36: CI run-registration lag handling.

Second concern of the slice (its own Gherkin scenario + two edge cases):
`make push` must tolerate CI registration lag so a regression is never
silently missed, and must fail safe (bounded) when a run never registers.
Reuses the approach-(a) harness (real git repos + the fake `gh` shim on PATH).

Recipe variants:
  push-buggy       : current production recipe (single discovery, no retry)
  push-fixed-retry : candidate fix (bounded retry around the SHA discovery)

Scenarios (all drive a LAGGING fake `gh`):
  lag-green : base GREEN / new GREEN, run registers after 2 polls
  lag-red   : base GREEN / new RED,   run registers after 2 polls  -> BLOCK
  never     : CI configured, run NEVER registers (astronomical)    -> bounded fail-safe
  no-ci     : NO CI configured (no .github/workflows/ files)        -> log + exit 0

Interactive knobs (the default invocation runs the full assertion matrix):

    uv run python spikes/prototypes/push-attribution/probe_retry.py
    uv run python spikes/prototypes/push-attribution/probe_retry.py \\
        --scenario never --poll-budget 3 --sleep 1

  --scenario     {lag-green|lag-red|never|all}   default: all
  --poll-budget  discovery attempts before the fail-safe block (default 10)
  --sleep        seconds slept between polls (default 0; production default is 1)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
MAKEFILE = SPIKE_DIR / "push-retry.mk"
FAKE_GH = SPIKE_DIR / "fake_gh.py"

DEFAULT_POLL_BUDGET = 10

SCENARIOS = {
    "lag-green": {"base": [], "new": [], "lag_polls": 2, "has_ci": True},
    "lag-red": {"base": [], "new": ["tests"], "lag_polls": 2, "has_ci": True},
    "never": {"base": [], "new": ["tests"], "lag_polls": 10**9, "has_ci": True},
    "no-ci": {"base": [], "new": ["tests"], "lag_polls": 0, "has_ci": False},
}

_ATTRIBUTION = (
    "\t  NEW=$$(gh run list --commit \"$$SHA\" --workflow \"$$WF\" --json databaseId --jq '.[0].databaseId'); \\\n"
    "\t  OLD=$$(gh run list --commit \"$$BASE\" --workflow \"$$WF\" --json databaseId --jq '.[0].databaseId'); \\\n"
    "\t  gh run watch \"$$NEW\" --exit-status >/dev/null 2>&1 || true; \\\n"
    "\t  NEWFAIL=$$(gh run view \"$$NEW\" --json jobs --jq '[.jobs[] | select(.conclusion==\"failure\") | .name] | sort | join(\",\")'); \\\n"
    "\t  if [ -z \"$$NEWFAIL\" ]; then echo \"$$WF: PASSED\"; continue; fi; \\\n"
    "\t  if [ -z \"$$OLD\" ]; then echo \"$$WF: FAILED ($$NEWFAIL) - unknown base, treating as YOUR regression\"; STATUS=1; continue; fi; \\\n"
    "\t  OLDFAIL=$$(gh run view \"$$OLD\" --json jobs --jq '[.jobs[] | select(.conclusion==\"failure\") | .name] | sort | join(\",\")'); \\\n"
    "\t  if [ \"$$NEWFAIL\" = \"$$OLDFAIL\" ]; then echo \"$$WF: pre-existing failure ($$NEWFAIL) - not yours\"; \\\n"
    "\t  else echo \"$$WF: NEW failure ($$NEWFAIL) - YOUR regression\"; STATUS=1; fi; \\\n"
)

_TAIL = "\tdone; \\\n\texit $$STATUS\n\n"


def _makefile_content() -> str:
    buggy = (
        ".PHONY: push-buggy push-fixed-retry\n"
        "\n"
        "RETRY_POLLS ?= 10\n"
        "RETRY_SLEEP ?= 1\n"
        "\n"
        "push-buggy:\n"
        "\tgit pull --rebase\n"
        "\tgit push\n"
        "\t@SHA=$$(git rev-parse HEAD); \\\n"
        "\tBASE=$$(git rev-parse origin/main); \\\n"
        "\tSTATUS=0; \\\n"
        "\techo \"Pushed $$SHA (base $$BASE)\"; \\\n"
        "\tfor WF in $$(gh run list --commit \"$$SHA\" --json workflowName --jq '.[].workflowName' | sort -u); do \\\n"
        + _ATTRIBUTION
        + _TAIL
    )
    fixed = (
        "push-fixed-retry:\n"
        "\tgit pull --rebase\n"
        "\t@BASE=$$(git rev-parse origin/main); \\\n"
        "\tSHA=$$(git rev-parse HEAD); \\\n"
        "\tgit push || exit $$?; \\\n"
        "\tif [ -z \"$$(ls .github/workflows/*.yml .github/workflows/*.yaml 2>/dev/null)\" ]; then \\\n"
        "\t  echo \"No CI configured - skipping attribution\"; \\\n"
        "\t  exit 0; \\\n"
        "\tfi; \\\n"
        "\tSTATUS=0; ATTEMPTS=0; WFS=\"\"; \\\n"
        "\twhile [ -z \"$$WFS\" ] && [ $$ATTEMPTS -lt $(RETRY_POLLS) ]; do \\\n"
        "\t  WFS=$$(gh run list --commit \"$$SHA\" --json workflowName --jq '.[].workflowName' | sort -u); \\\n"
        "\t  [ -n \"$$WFS\" ] && break; \\\n"
        "\t  ATTEMPTS=$$((ATTEMPTS + 1)); \\\n"
        "\t  sleep $(RETRY_SLEEP); \\\n"
        "\tdone; \\\n"
        "\techo \"Pushed $$SHA (base $$BASE) after $$ATTEMPTS poll(s)\"; \\\n"
        "\tif [ -z \"$$WFS\" ]; then \\\n"
        "\t  echo \"CI: no run registered for $$SHA after $(RETRY_POLLS) poll(s) - fail-safe block\"; \\\n"
        "\t  exit 1; \\\n"
        "\tfi; \\\n"
        "\tfor WF in $$WFS; do \\\n"
        + _ATTRIBUTION
        + _TAIL
    )
    return buggy + fixed + "%:\n\t@:\n"


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


def _setup(root, name, base_fail, new_fail, has_ci):
    origin = root / f"{name}-origin.git"
    work = root / f"{name}-work"
    _run(["git", "init", "--bare", "-q", str(origin)], cwd=root)
    _run(["git", "init", "-q", str(work)], cwd=root)
    if has_ci:
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

    gh_state = root / f"{name}-gh.json"
    if has_ci:
        gh_state.write_text(
            json.dumps(
                {
                    base: {"workflows": {"CI": {"run_id": "base-run", "failures": base_fail}}},
                    new: {"workflows": {"CI": {"run_id": "new-run", "failures": new_fail}}},
                }
            ),
            encoding="utf-8",
        )
    else:
        gh_state.write_text(json.dumps({}), encoding="utf-8")

    fake_bin = root / f"{name}-fake-bin"
    fake_bin.mkdir()
    shim = fake_bin / "gh"
    shim.write_text(
        "#!/bin/sh\n" f'exec "{sys.executable}" "{FAKE_GH}" "$@"\n',
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return work, fake_bin, gh_state, base, new


def _run_recipe(
    work, fake_bin, gh_state, target, lag_sha, lag_polls, lag_file, poll_budget, sleep
):
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
    env["FAKE_GH_STATE"] = str(gh_state)
    env["FAKE_GH_LAG_SHA"] = lag_sha
    env["FAKE_GH_LAG_POLLS"] = str(lag_polls)
    env["FAKE_GH_LAG_FILE"] = str(lag_file)
    return _run(
        [
            "make", "-C", str(work), "-f", str(MAKEFILE), target,
            f"RETRY_POLLS={poll_budget}", f"RETRY_SLEEP={sleep}",
        ],
        cwd=work,
        env=env,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Interactive runner for slice 00-36 CI-registration-lag "
        "behaviour.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scenario",
        choices=[*SCENARIOS, "all"],
        default="all",
        help="Which scenario to drive (default: all).",
    )
    parser.add_argument(
        "--poll-budget",
        type=int,
        default=DEFAULT_POLL_BUDGET,
        help="Discovery attempts before the fail-safe block (default: 10).",
    )
    parser.add_argument(
        "--sleep",
        type=int,
        default=0,
        help="Seconds slept between polls (default: 0; production default is 1).",
    )
    args = parser.parse_args()

    selected = (
        SCENARIOS
        if args.scenario == "all"
        else {args.scenario: SCENARIOS[args.scenario]}
    )
    assert_full_matrix = (
        args.scenario == "all"
        and args.poll_budget == DEFAULT_POLL_BUDGET
        and args.sleep == 0
    )

    MAKEFILE.write_text(_makefile_content(), encoding="utf-8")
    root = Path(tempfile.mkdtemp(prefix="teddy-push-retry-"))
    results = {}
    try:
        for scenario, io in selected.items():
            for target in ("push-buggy", "push-fixed-retry"):
                name = f"{scenario}-{target}"
                work, fake_bin, gh_state, base, new = _setup(
                    root, name, io["base"], io["new"], io["has_ci"]
                )
                lag_file = root / f"{name}-lag.count"
                res = _run_recipe(
                    work, fake_bin, gh_state, target, new, io["lag_polls"],
                    lag_file, args.poll_budget, args.sleep,
                )
                results[(target, scenario)] = {
                    "rc": res.returncode,
                    "out": res.stdout,
                    "err": res.stderr,
                    "base": base,
                    "new": new,
                }

        print("=" * 72)
        print(
            f"RAW TRANSCRIPT (registration lag) | scenario={args.scenario} "
            f"budget={args.poll_budget} sleep={args.sleep}"
        )
        print("=" * 72)
        for (target, scenario), r in results.items():
            print(f"### {target} / {scenario}")
            print(f"    base={r['base'][:8]} new={r['new'][:8]}")
            body = r["out"].rstrip() or "(no stdout)"
            for line in body.splitlines():
                print("    " + line)
            print(f"    --> exit={r['rc']}\n")

        if not assert_full_matrix:
            print("=" * 72)
            print(
                "INSPECTION MODE (non-default knobs) - assertions run only on "
                "the default full matrix."
            )
            print("=" * 72)
            return 0

        buggy_lag_red = results[("push-buggy", "lag-red")]
        fixed_lag_red = results[("push-fixed-retry", "lag-red")]
        fixed_lag_green = results[("push-fixed-retry", "lag-green")]
        fixed_never = results[("push-fixed-retry", "never")]
        buggy_no_ci = results[("push-buggy", "no-ci")]
        fixed_no_ci = results[("push-fixed-retry", "no-ci")]

        checks = [
            (
                "buggy under lag: regression silently missed (silent exit 0)",
                buggy_lag_red["rc"] == 0
                and "YOUR regression" not in buggy_lag_red["out"],
            ),
            (
                "fixed under lag: retried by polling (2 polls)",
                "after 2 poll(s)" in fixed_lag_red["out"],
            ),
            (
                "fixed under lag: base is the pre-push tip",
                f"base {fixed_lag_red['base']}" in fixed_lag_red["out"],
            ),
            (
                "fixed under lag: regression reported as YOUR regression (blocks)",
                fixed_lag_red["rc"] != 0
                and "YOUR regression" in fixed_lag_red["out"],
            ),
            (
                "fixed under lag: green run passes",
                fixed_lag_green["rc"] == 0 and "PASSED" in fixed_lag_green["out"],
            ),
            (
                "fixed, run never registers: bounded fail-safe block (10 polls)",
                fixed_never["rc"] != 0
                and "fail-safe" in fixed_never["out"]
                and "after 10 poll(s)" in fixed_never["out"],
            ),
            (
                "fixed, no CI configured: logs a notice and exits 0 (non-blocking)",
                fixed_no_ci["rc"] == 0 and "No CI configured" in fixed_no_ci["out"],
            ),
            (
                "buggy, no CI configured: silent (no notice) - the log is new",
                "No CI configured" not in buggy_no_ci["out"],
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