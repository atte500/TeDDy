"""Behavioural probe for slice 00-36 (`make push` CI attribution).

Approach (a) validation: drive the REAL recipe bodies through `make` inside a
throwaway git repo (REAL `git`) with a fake `gh` shim prepended to PATH.

Recipe variants compared:
  push-buggy : the current production recipe (BASE captured AFTER `git push`)
  push-fixed : candidate fix (BASE captured BEFORE `git push`)

CI scenarios:
  regression  : base GREEN, pushed commit RED (job "tests")  -> must BLOCK
  preexisting : base RED,   pushed commit RED (same jobs)     -> must PASS

The defect manifests as `push-buggy` exiting 0 on `regression` (a real
regression silently misclassified as pre-existing).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SPIKE_DIR = Path(__file__).resolve().parent
MAKEFILE = SPIKE_DIR / "push.mk"
FAKE_GH = SPIKE_DIR / "fake_gh.py"

SCENARIOS = {
    "regression": {"base": [], "new": ["tests"]},
    "preexisting": {"base": ["tests"], "new": ["tests"]},
}


def _makefile_content() -> str:
    def attribution_block(capture_base_first: bool) -> str:
        if capture_base_first:
            head = (
                "\t@BASE=$$(git rev-parse origin/main); \\\n"
                "\tSHA=$$(git rev-parse HEAD); \\\n"
                "\tgit push || exit $$?; \\\n"
                "\tSTATUS=0; \\\n"
            )
        else:
            head = (
                "\t@SHA=$$(git rev-parse HEAD); \\\n"
                "\tBASE=$$(git rev-parse origin/main); \\\n"
                "\tSTATUS=0; \\\n"
            )
        body = (
            '\techo "Pushed $$SHA (base $$BASE)"; \\\n'
            "\tfor WF in $$(gh run list --commit \"$$SHA\" --json workflowName "
            "--jq '.[].workflowName' | sort -u); do \\\n"
            "\t  NEW=$$(gh run list --commit \"$$SHA\" --workflow \"$$WF\" "
            "--json databaseId --jq '.[0].databaseId'); \\\n"
            "\t  OLD=$$(gh run list --commit \"$$BASE\" --workflow \"$$WF\" "
            "--json databaseId --jq '.[0].databaseId'); \\\n"
            '\t  gh run watch "$$NEW" --exit-status >/dev/null 2>&1 || true; \\\n'
            "\t  NEWFAIL=$$(gh run view \"$$NEW\" --json jobs --jq "
            "'[.jobs[] | select(.conclusion==\"failure\") | .name] | sort | "
            "join(\",\")'); \\\n"
            '\t  if [ -z "$$NEWFAIL" ]; then echo "$$WF: PASSED"; continue; fi; \\\n'
            "\t  if [ -z \"$$OLD\" ]; then echo \"$$WF: FAILED ($$NEWFAIL) - "
            'unknown base, treating as YOUR regression"; STATUS=1; continue; fi; \\\n'
            "\t  OLDFAIL=$$(gh run view \"$$OLD\" --json jobs --jq "
            "'[.jobs[] | select(.conclusion==\"failure\") | .name] | sort | "
            "join(\",\")'); \\\n"
            "\t  if [ \"$$NEWFAIL\" = \"$$OLDFAIL\" ]; then echo \"$$WF: "
            'pre-existing failure ($$NEWFAIL) - not yours"; \\\n'
            "\t  else echo \"$$WF: NEW failure ($$NEWFAIL) - YOUR "
            'regression"; STATUS=1; fi; \\\n'
            "\tdone; \\\n"
            "\texit $$STATUS\n"
        )
        return head + body

    lines = [
        ".PHONY: push-buggy push-fixed",
        "",
        "push-buggy:",
        "\tgit pull --rebase",
        "\tgit push",
        attribution_block(capture_base_first=False).rstrip("\n"),
        "",
        "push-fixed:",
        "\tgit pull --rebase",
        attribution_block(capture_base_first=True).rstrip("\n"),
        "",
        "%:",
        "\t@:",
        "",
    ]
    return "\n".join(lines)


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


def _setup(root: Path, name: str, base_fail, new_fail):
    origin = root / f"{name}-origin.git"
    work = root / f"{name}-work"
    _run(["git", "init", "--bare", "-q", str(origin)], cwd=root)
    _run(["git", "init", "-q", str(work)], cwd=root)
    _git(work, "commit", "--allow-empty", "-q", "-m", "base")
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
                base: {"workflows": {"CI": {"run_id": "base-run", "failures": base_fail}}},
                new: {"workflows": {"CI": {"run_id": "new-run", "failures": new_fail}}},
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


def _run_recipe(work, fake_bin, gh_state, target):
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(fake_bin), env.get("PATH", "")])
    env["FAKE_GH_STATE"] = str(gh_state)
    return _run(
        ["make", "-C", str(work), "-f", str(MAKEFILE), target],
        cwd=work,
        env=env,
        check=False,
    )


def main() -> int:
    MAKEFILE.write_text(_makefile_content(), encoding="utf-8")
    root = Path(tempfile.mkdtemp(prefix="teddy-push-attrib-"))
    results = {}
    try:
        for scenario, io in SCENARIOS.items():
            for target in ("push-buggy", "push-fixed"):
                name = f"{scenario}-{target}"
                work, fake_bin, gh_state, base, new = _setup(
                    root, name, io["base"], io["new"]
                )
                before = _git(work, "rev-parse", "origin/main").stdout.strip()
                res = _run_recipe(work, fake_bin, gh_state, target)
                after = _git(work, "rev-parse", "origin/main").stdout.strip()
                results[(target, scenario)] = {
                    "rc": res.returncode,
                    "out": res.stdout,
                    "err": res.stderr,
                    "base": base,
                    "new": new,
                    "before": before,
                    "after": after,
                }

        print("=" * 72)
        print("RAW TRANSCRIPT")
        print("=" * 72)
        for (target, scenario), r in results.items():
            print(f"### {target} / {scenario}")
            print(
                f"    base={r['base'][:8]} new={r['new'][:8]} "
                f"origin/main before={r['before'][:8]} after={r['after'][:8]}"
            )
            body = r["out"].rstrip() or "(no stdout)"
            for line in body.splitlines():
                print("    " + line)
            print(f"    --> exit={r['rc']}\n")

        buggy_reg = results[("push-buggy", "regression")]
        fixed_reg = results[("push-fixed", "regression")]
        fixed_pre = results[("push-fixed", "preexisting")]

        checks = [
            (
                "git push advanced origin/main (bug mechanism confirmed)",
                buggy_reg["after"] == buggy_reg["new"],
            ),
            (
                "buggy/regression: base collapsed onto the pushed SHA",
                f"base {buggy_reg['new']}" in buggy_reg["out"],
            ),
            (
                "buggy/regression: real regression misclassified (silent exit 0)",
                buggy_reg["rc"] == 0 and "pre-existing" in buggy_reg["out"],
            ),
            (
                "fixed/regression: base is the pre-push tip",
                f"base {fixed_reg['base']}" in fixed_reg["out"],
            ),
            (
                "fixed/regression: reported as YOUR regression (blocks)",
                fixed_reg["rc"] != 0 and "YOUR regression" in fixed_reg["out"],
            ),
            (
                "fixed/preexisting: reported pre-existing (exit 0)",
                fixed_pre["rc"] == 0 and "pre-existing" in fixed_pre["out"],
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