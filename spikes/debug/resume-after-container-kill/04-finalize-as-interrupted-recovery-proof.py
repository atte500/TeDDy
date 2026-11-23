#!/usr/bin/env python3
"""MRE-04: finalizing the interrupted turn as INTERRUPTED ends the stuck state
and hands off to a fresh plan in the next turn.

Status quo (MRE-01 + MRE-02): a hard kill leaves plan.md with no report.md, so
the turn reads PENDING_PLAN; bare resume replays the plan from action 1 and
pre-flight rejects the action the killed run already applied.

Proposed design: on resume, synthesize an INTERRUPTED report for the
interrupted turn, finalize it (write report.md + create the next turn), record
the resume reply as the turn's user request, and plan the NEXT turn from
scratch against the observed workspace. Every step is a shipped composition:
`_handle_aborted_execution` already synthesizes a per-action log list,
`trigger_replan` already finalizes-then-plans, and `_consume_awaiting_reply`
already synthesizes-finalizes-preserves.

This MRE runs that chain on a real killed workspace using the REAL parser,
REAL plan validator, REAL ExecutionReportAssembler, REAL SessionService /
SessionRepository / LocalFileSystemAdapter, and the REAL
SessionLifecycleManager.finalize_turn. Only the report formatter, planner,
replanner and interactor are stubs: the assertion under test is the
sequencing, and the formatter's `## User Request` contract is verified by
inspecting `execution_report.md.j2:322-325`.

Run:
  uv run python spikes/debug/resume-after-container-kill/04-finalize-as-interrupted-recovery-proof.py
"""

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from teddy_executor.adapters.outbound.local_file_system_adapter import (  # noqa: E402
    LocalFileSystemAdapter,
)
from teddy_executor.core.domain.models import (  # noqa: E402
    ActionLog,
    ActionStatus,
    ReportAssemblyData,
    RunStatus,
)
from teddy_executor.core.domain.models.planning_ports import SessionPorts  # noqa: E402
from teddy_executor.core.ports.outbound.session_manager import SessionState  # noqa: E402
from teddy_executor.core.services.execution_report_assembler import (  # noqa: E402
    ExecutionReportAssembler,
)
from teddy_executor.core.services.markdown_plan_parser import (  # noqa: E402
    MarkdownPlanParser,
)
from teddy_executor.core.services.plan_validator import PlanValidator  # noqa: E402
from teddy_executor.core.services.session_lifecycle_manager import (  # noqa: E402
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_repository import SessionRepository  # noqa: E402
from teddy_executor.core.services.session_service import SessionService  # noqa: E402
from teddy_executor.core.services.validation_rules.execute import (  # noqa: E402
    ExecuteActionValidator,
)
from teddy_executor.core.services.validation_rules.filesystem import (  # noqa: E402
    CreateActionValidator,
)

SESSION_NAME = "20260101_000000-migration"
APPLIED_ARTIFACT = "applied-before-kill.txt"
REPLY = "skip the killed action and finish the migration"
HONESTY_NOTE = (
    "Outcome not recorded: the running process was terminated ungracefully; "
    "this action may or may not have applied."
)

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

META = """turn_id: '01'
agent_name: developer
cumulative_cost: 0.0
turn_cost: 0.0
creation_timestamp: '2026-01-01T00:00:00+00:00'
"""


class _StubEditSimulator:
    def simulate_edits(self, content, edits, threshold=0.0, match_all=False):
        raise AssertionError("edit simulator is not used by this MRE")


class _FrozenTime:
    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now_utc(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class _StubConfig:
    def get_setting(self, key, default=None):
        return default


class _StubPromptManager:
    def get_available_agents(self):
        return []

    def fetch_system_prompt(self, agent_name, turn_path):
        return ""


class _StubInitService:
    def ensure_initialized(self):
        return None


class _MarkerReportFormatter:
    """Mirrors the template's user-request block (execution_report.md.j2:322-325)."""

    def format(self, report):
        return (
            f"# Execution Report: {report.plan_title}\n"
            f"- **Overall Status:** {report.run_summary.status.value}\n\n"
            f"## User Request\n{report.user_request}\n"
        )


class _StubInteractor:
    def ask_question(self, prompt):
        raise AssertionError(f"recovery must not prompt, but asked: {prompt}")

    def display_message(self, message):
        print(f"DISPLAY: {message}")


class _StubPlanner:
    def trigger_new_plan(self, turn_dir, message=None):
        raise AssertionError("the next turn's plan is triggered by the caller")


class _StubReplanner:
    def build_failure_report(self, *args, **kwargs):
        raise AssertionError("recovery must not build a validation-failure report")

    def trigger_replan_turn(self, *args, **kwargs):
        raise AssertionError("recovery must not replan from a failure report")


class _StubSystemEnvironment:
    def isatty(self):
        return True


def build_killed_workspace(root: Path) -> Path:
    session_dir = root / ".teddy" / "sessions" / SESSION_NAME
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "plan.md").write_text(PENDING_PLAN, encoding="utf-8")
    (turn_dir / "meta.yaml").write_text(META, encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    (session_dir / "session.context").write_text("", encoding="utf-8")
    (root / APPLIED_ARTIFACT).write_text(
        "written before the container was killed\n", encoding="utf-8"
    )
    return turn_dir


def action_type_name(action) -> str:
    return str(getattr(action.type, "value", action.type))


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        turn_dir = build_killed_workspace(root)
        plan_path = (turn_dir / "plan.md").as_posix()

        adapter = LocalFileSystemAdapter(_StubEditSimulator(), root_dir=str(root))
        service = SessionService(
            file_system_manager=adapter,
            repository=SessionRepository(adapter),
            time_service=_FrozenTime(),
            prompt_manager=_StubPromptManager(),
            init_service=_StubInitService(),
            config_service=_StubConfig(),
        )
        manager = SessionLifecycleManager(
            SessionPorts(
                session_service=service,
                file_system_manager=adapter,
                report_formatter=_MarkerReportFormatter(),
                user_interactor=_StubInteractor(),
                session_planner=_StubPlanner(),
                replanner=_StubReplanner(),
                plan_parser=MarkdownPlanParser(),
                time_service=_FrozenTime(),
                report_assembler=ExecutionReportAssembler(),
                system_environment=_StubSystemEnvironment(),
            )
        )
        parser = MarkdownPlanParser()

        state, latest = service.get_session_state(SESSION_NAME)
        print(f"killed state          : {state.name} at {latest}")
        print(f"report.md present     : {adapter.path_exists(f'{latest}/report.md')}")
        print(f"workspace already hit : {adapter.path_exists(APPLIED_ARTIFACT)}")
        assert state is SessionState.PENDING_PLAN

        # 1. Status quo: replaying the plan is rejected in pre-flight.
        validator = PlanValidator(
            adapter,
            validators=[
                CreateActionValidator(adapter),
                ExecuteActionValidator(adapter),
            ],
        )
        replay_errors = validator.validate(
            parser.parse(PENDING_PLAN, plan_path=plan_path)
        )
        print(f"status-quo pre-flight : {replay_errors[0].message}")
        assert any("File already exists" in e.message for e in replay_errors)

        # 2. Recovery: synthesize the INTERRUPTED report for the killed turn.
        plan = parser.parse(PENDING_PLAN, plan_path=plan_path)
        logs = []
        for action in plan.actions:
            params = dict(action.params)
            if action.description:
                params["Description"] = action.description
            logs.append(
                ActionLog(
                    status=ActionStatus.INTERRUPTED,
                    action_type=action_type_name(action),
                    params=params,
                    details=HONESTY_NOTE,
                )
            )
        report = ExecutionReportAssembler().assemble(
            ReportAssemblyData(
                plan=plan,
                action_logs=logs,
                start_time=_FrozenTime().now_utc(),
                message=REPLY,
                is_session=True,
            )
        )
        print(f"recovered run status  : {report.run_summary.status.value}")
        print(f"recovered user request: {report.user_request!r}")
        assert report.run_summary.status is RunStatus.INTERRUPTED
        assert report.user_request == REPLY

        # 3. Finalize the interrupted turn (no execution behind the report).
        next_turn_dir = manager.finalize_turn(plan_path, report, plan=plan)
        next_dir = Path(next_turn_dir)
        next_id = next_dir.name
        print(f"next turn created     : {next_turn_dir}")

        report_text = (turn_dir / "report.md").read_text(encoding="utf-8")
        print(f"interrupted report    : {turn_dir / 'report.md'} written")
        assert "INTERRUPTED" in report_text
        assert "## User Request" in report_text

        assert next_id == "02", next_id
        assert (next_dir / "meta.yaml").exists(), next_dir
        assert (next_dir / "turn.context").exists(), next_dir

        # 4. The abandoned plan is carried forward into the prune-exempt scope.
        preserved = (root / ".teddy" / "sessions" / SESSION_NAME / "session.context")
        preserved_paths = set(preserved.read_text(encoding="utf-8").split())
        expected = {
            f".teddy/sessions/{SESSION_NAME}/01/plan.md",
            f".teddy/sessions/{SESSION_NAME}/01/report.md",
        }
        print(f"preserved in session  : {sorted(preserved_paths)}")
        assert expected <= preserved_paths, preserved_paths

        # 5. The state machine is left in a state it already handles by planning.
        state_after, latest_after = service.get_session_state(SESSION_NAME)
        print(f"state after recovery  : {state_after.name} at {latest_after}")
        assert state_after is SessionState.EMPTY
        assert latest_after.endswith("/02")

    print()
    print("PASS: synthesizing an INTERRUPTED report and finalizing the killed")
    print("      turn converts the unrecoverable PENDING_PLAN into a finalized")
    print("      turn plus an empty next turn, carries the abandoned plan into")
    print("      the prune-exempt session.context, and leaves the state machine")
    print("      ready for a fresh plan -- no replay, no pre-flight rejection.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
