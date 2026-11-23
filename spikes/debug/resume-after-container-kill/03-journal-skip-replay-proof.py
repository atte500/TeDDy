#!/usr/bin/env python3
"""MRE-03: a per-turn action journal lets a resumed PENDING_PLAN turn skip the
actions the killed run already applied, so pre-flight does not block and the
remaining actions still run.

Status quo (MRE-01 + MRE-02): bare resume replays plan.md from action 1 and
pre-flight rejects the already-applied CREATE with "File already exists".

Proposed fix: persist each completed action's outcome to a durable per-turn
journal as it finishes; on resume, re-hydrate those outcomes and validate /
dispatch only the pending actions.

This is a sandbox replica of that mechanism. It reuses the REAL parser,
PlanValidator, and action validators so the pre-flight behaviour under test is
production code; only the dispatch loop and the journal are the prototype the
production change would thread through SessionOrchestrator /
ExecutionOrchestrator.

Run:
  uv run python spikes/debug/resume-after-container-kill/03-journal-skip-replay-proof.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from teddy_executor.adapters.outbound.local_file_system_adapter import (  # noqa: E402
    LocalFileSystemAdapter,
)
from teddy_executor.core.services.markdown_plan_parser import (  # noqa: E402
    MarkdownPlanParser,
)
from teddy_executor.core.services.plan_validator import PlanValidator  # noqa: E402
from teddy_executor.core.services.validation_rules.execute import (  # noqa: E402
    ExecuteActionValidator,
)
from teddy_executor.core.services.validation_rules.filesystem import (  # noqa: E402
    CreateActionValidator,
)

SESSION_NAME = "20260101_000000-migration"
APPLIED_ARTIFACT = "applied-before-kill.txt"

PENDING_PLAN = """# Apply the migration edits
- **Status:** ON-TRACK 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
~~~~~~
### Summary
The killed run was half-way through the migration.

### Expectation
The second line is appended to applied-before-kill.txt.

### Progress
Goal: finish the migration.

### Notes
- Simulated state after an ungraceful kill.
~~~~~~

## Action Plan

### `CREATE`
- **File Path:** applied-before-kill.txt
- **Description:** Already written by the run that was killed.
~~~~~~
written before the container was killed
~~~~~~

### `EXECUTE`
- **Description:** Append a second line to the same file.
- **Expected Outcome:** The file grows by one line.
~~~~~~
echo "second line" >> applied-before-kill.txt
~~~~~~
"""


class _StubEditSimulator:
    def simulate_edits(self, content, edits, threshold=0.0, match_all=False):
        raise AssertionError("edit simulator is not used by this MRE")


class SimulatedKill(Exception):
    """Models the process dying between two actions (no finally/abort runs)."""


class _PlanSlice:
    """Exposes only .actions, the sole attribute PlanValidator.validate reads."""

    def __init__(self, actions):
        self.actions = actions


class JournaledReplay:
    """Prototype of the production fix: journal each completed action, and on
    resume validate + dispatch only the pending actions."""

    def __init__(self, adapter, parser, validator, workspace_root, turn_dir, kill_after_index=None):
        self._adapter = adapter
        self._parser = parser
        self._validator = validator
        self._root = workspace_root
        self._journal_path = turn_dir / "action_journal.json"
        self._kill_after_index = kill_after_index
        self.skipped = []
        self.dispatched = []

    def _load_journal(self):
        if not self._journal_path.exists():
            return []
        return json.loads(self._journal_path.read_text(encoding="utf-8"))

    def _save_journal(self, entries):
        tmp = self._journal_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(entries), encoding="utf-8")
        os.replace(tmp, self._journal_path)

    def _apply(self, action):
        if action.type.upper() == "CREATE":
            target = self._root / action.params["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(action.params["content"], encoding="utf-8")
        elif action.type.upper() == "EXECUTE":
            subprocess.run(
                action.params["command"], shell=True, cwd=self._root, check=True
            )

    def run(self, plan_path):
        plan = self._parser.parse(
            self._adapter.read_raw_file(plan_path), plan_path=plan_path
        )
        journal = self._load_journal()
        done = {entry["index"] for entry in journal}

        pending = [a for i, a in enumerate(plan.actions) if i not in done]
        errors = self._validator.validate(_PlanSlice(pending))
        if errors:
            raise RuntimeError(
                "pre-flight rejected the replay:\n"
                + "\n".join(f"  - {e.message}" for e in errors)
            )

        for index, action in enumerate(plan.actions):
            if index in done:
                self.skipped.append(action.type)
                continue
            self._apply(action)
            self.dispatched.append(action.type)
            journal.append({"index": index, "type": action.type, "status": "SUCCESS"})
            self._save_journal(journal)
            if self._kill_after_index == index:
                raise SimulatedKill()
        return journal


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        turn_dir = root / ".teddy" / "sessions" / SESSION_NAME / "01"
        turn_dir.mkdir(parents=True, exist_ok=True)
        plan_path_obj = turn_dir / "plan.md"
        plan_path_obj.write_text(PENDING_PLAN, encoding="utf-8")
        plan_path = plan_path_obj.as_posix()

        adapter = LocalFileSystemAdapter(_StubEditSimulator(), root_dir=str(root))
        parser = MarkdownPlanParser()
        validator = PlanValidator(
            adapter,
            validators=[
                CreateActionValidator(adapter),
                ExecuteActionValidator(adapter),
            ],
        )
        artifact = root / APPLIED_ARTIFACT
        journal_file = turn_dir / "action_journal.json"

        # Phase A: the killed run completes the CREATE, journals it, then dies
        # before the EXECUTE (models SIGKILL between actions).
        killed = JournaledReplay(
            adapter, parser, validator, root, turn_dir, kill_after_index=0
        )
        try:
            killed.run(plan_path)
            raise AssertionError("expected the simulated kill to interrupt phase A")
        except SimulatedKill:
            pass
        journal_after_kill = json.loads(journal_file.read_text(encoding="utf-8"))
        print(f"phase A dispatched   : {killed.dispatched}")
        print(f"journal after kill   : {journal_after_kill}")
        print(f"artifact after kill  : {artifact.read_text(encoding='utf-8').splitlines()!r}")
        assert killed.dispatched == ["CREATE"], killed.dispatched
        assert len(artifact.read_text(encoding="utf-8").splitlines()) == 1

        # Control: bare resume with NO journal (status quo = MRE-01 + MRE-02).
        journal_file.unlink()
        control = JournaledReplay(adapter, parser, validator, root, turn_dir)
        try:
            control.run(plan_path)
            raise AssertionError("expected the status-quo replay to be rejected pre-flight")
        except RuntimeError as exc:
            print(f"control pre-flight   : {str(exc).splitlines()[1].strip()}")
            assert "File already exists" in str(exc)

        # Fix: restore the journal and resume with the journal-skip mechanism.
        journal_file.write_text(json.dumps(journal_after_kill), encoding="utf-8")
        fixed = JournaledReplay(adapter, parser, validator, root, turn_dir)
        fixed.run(plan_path)
        lines = artifact.read_text(encoding="utf-8").splitlines()
        print(f"fix dispatched       : {fixed.dispatched}")
        print(f"fix skipped          : {fixed.skipped}")
        print(f"artifact after resume: {lines!r}")
        assert fixed.skipped == ["CREATE"], fixed.skipped
        assert fixed.dispatched == ["EXECUTE"], fixed.dispatched
        assert len(lines) == 2, lines

    print()
    print("PASS: with a per-turn action journal, bare resume skips the action")
    print("      the killed run already applied, passes pre-flight, and runs")
    print("      only the pending action -- no manual .teddy/ surgery, no -m.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
