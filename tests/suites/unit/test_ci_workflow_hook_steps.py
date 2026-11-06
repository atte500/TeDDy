"""Guardrail: each CI quality hook runs in its own pre-commit invocation.

``pre-commit run`` binds a single hook id positional, so a step that passes two
ids aborts with ``unrecognized arguments`` before running either hook, and a
shell loop over hook ids hides the failing hook behind one shared step verdict.
This test pins that every invocation in the CI workflow names exactly one hook
id declared in ``.pre-commit-config.yaml``.
"""

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
CONFIG = REPO_ROOT / ".pre-commit-config.yaml"


def _declared_hook_ids() -> set[str]:
    text = CONFIG.read_text(encoding="utf-8")
    return set(re.findall(r"^\s*-\s+id:\s+(\S+)\s*$", text, re.MULTILINE))


def _run_blocks() -> list[str]:
    """Return every shell `run` block, so prose and YAML comments never match."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    runs: list[str] = []
    for job in workflow.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = step.get("run")
            if run:
                runs.append(run)
    return runs


def _invoked_hook_tokens() -> list[list[str]]:
    invocations: list[list[str]] = []
    for block in _run_blocks():
        for line in block.splitlines():
            match = re.search(r"pre-commit run (.+)$", line)
            if not match:
                continue
            invocations.append([t.strip('"') for t in match.group(1).split()])
    return invocations


def test_each_quality_step_invokes_exactly_one_declared_hook():
    invocations = _invoked_hook_tokens()
    assert invocations, "expected the CI workflow to invoke pre-commit"

    declared = _declared_hook_ids()
    for tokens in invocations:
        # The hook id is the leading positional; flags and their values may
        # follow (`--all-files`, `--hook-stage manual`).
        assert tokens[0] in declared, f"unknown hook id: {tokens[0]}"
        extra_hooks = [t for t in tokens[1:] if t in declared]
        assert not extra_hooks, (
            f"`pre-commit run` takes one hook id, got: {' '.join(tokens)}"
        )
