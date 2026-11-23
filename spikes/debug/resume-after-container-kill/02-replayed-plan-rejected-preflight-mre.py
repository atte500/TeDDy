#!/usr/bin/env python3
"""MRE-02: the replayed plan is rejected in pre-flight on the already-applied action.

Chains off MRE-01. Bare `teddy resume` on a PENDING_PLAN turn hands
`plan.md` back to the orchestrator with no record of which actions the
killed run already executed. The orchestrator parses that plan and runs
pre-flight validation against the live workspace.

The killed run had already applied the plan's first action (a CREATE), so
pre-flight returns "File already exists" for that target. The replay cannot
proceed; the only exits are the automated replan (a fresh LLM plan against a
mutated workspace) or manually rolling back the turn artifacts -- the
workaround the bug report describes.

Run:
  uv run python spikes/debug/resume-after-container-kill/02-replayed-plan-rejected-preflight-mre.py
"""

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


def build_killed_workspace(root: Path) -> Path:
    """Recreate the state MRE-01 proved bare resume dispatches against."""
    turn_dir = root / ".teddy" / "sessions" / SESSION_NAME / "01"
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "plan.md").write_text(PENDING_PLAN, encoding="utf-8")
    (root / APPLIED_ARTIFACT).write_text(
        "written before the container was killed\n", encoding="utf-8"
    )
    return turn_dir


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        turn_dir = build_killed_workspace(root)
        plan_path = (turn_dir / "plan.md").as_posix()

        adapter = LocalFileSystemAdapter(_StubEditSimulator(), root_dir=str(root))
        parser = MarkdownPlanParser()
        validator = PlanValidator(
            adapter,
            validators=[
                CreateActionValidator(adapter),
                ExecuteActionValidator(adapter),
            ],
        )

        plan = parser.parse(PENDING_PLAN, plan_path=plan_path)
        print(f"replayed plan actions: {[a.type for a in plan.actions]}")
        for action in plan.actions:
            print(f"  {action.type} params    : {sorted(action.params)}")
        print(f"target already exists: {adapter.path_exists(APPLIED_ARTIFACT)}")

        errors = validator.validate(plan)
        print(f"pre-flight errors    : {len(errors)}")
        for error in errors:
            print(f"  - {error.message}")

        assert errors, "expected the replayed plan to fail pre-flight"
        assert any("File already exists" in e.message for e in errors), errors

    print()
    print("PASS: the plan bare resume replays is rejected in pre-flight on the")
    print("      action the killed run already applied, so the turn can only")
    print("      continue via the automated replan or manual .teddy/ rollback.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
