#!/usr/bin/env python3
"""MRE-01: bare `teddy resume` on a PENDING_PLAN turn replays plan.md from action 1.

Simulated ungraceful kill (container kill / SIGKILL):
  The killed run had already written plan.md and applied its first mutating
  action, then died before `finalize_turn` wrote report.md. The turn
  directory therefore holds plan.md + meta.yaml + turn.context but no
  report.md  ->  SessionState.PENDING_PLAN.

Question: what does `teddy resume` (no -m) dispatch to?

Run:
  uv run python spikes/debug/resume-after-container-kill/01-pending-plan-bare-resume-mre.py
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
from teddy_executor.core.domain.models.planning_ports import SessionPorts  # noqa: E402
from teddy_executor.core.services.session_lifecycle_manager import (  # noqa: E402
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_repository import SessionRepository  # noqa: E402
from teddy_executor.core.services.session_service import SessionService  # noqa: E402

SESSION_NAME = "20260101_000000-migration"
APPLIED_ARTIFACT = "applied-before-kill.txt"

PENDING_PLAN = """# Apply the migration edits

## Rationale
1. Synthesis
The killed run was half-way through the migration.

## Action Plan

### `CREATE`
- **File Path:** `applied-before-kill.txt`
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


class _StubReportFormatter:
    def format(self, report):
        return ""


class _StubInteractor:
    def ask_question(self, prompt):
        raise AssertionError(f"bare resume must not prompt, but asked: {prompt}")

    def display_message(self, message):
        print(f"DISPLAY: {message}")


class _StubPlanner:
    def trigger_new_plan(self, turn_dir, message=None):
        raise AssertionError("bare resume on PENDING_PLAN must not plan")


class _StubReplanner:
    def build_failure_report(self, *args, **kwargs):
        raise AssertionError("not reached")

    def trigger_replan_turn(self, *args, **kwargs):
        raise AssertionError("not reached")


class _StubSystemEnvironment:
    def __init__(self, isatty):
        self._isatty = isatty

    def isatty(self):
        return self._isatty


class _RecordingOrchestrator:
    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(kwargs)
        return None


def build_killed_workspace(root: Path) -> None:
    turn_dir = root / ".teddy" / "sessions" / SESSION_NAME / "01"
    turn_dir.mkdir(parents=True, exist_ok=True)
    (turn_dir / "plan.md").write_text(PENDING_PLAN, encoding="utf-8")
    (turn_dir / "meta.yaml").write_text(META, encoding="utf-8")
    (turn_dir / "turn.context").write_text("", encoding="utf-8")
    # The mutating action the killed run already applied:
    (root / APPLIED_ARTIFACT).write_text(
        "written before the container was killed\n", encoding="utf-8"
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        build_killed_workspace(root)

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
                report_formatter=_StubReportFormatter(),
                user_interactor=_StubInteractor(),
                session_planner=_StubPlanner(),
                replanner=_StubReplanner(),
                system_environment=_StubSystemEnvironment(isatty=True),
            )
        )
        orchestrator = _RecordingOrchestrator()

        state, turn_path = service.get_session_state(SESSION_NAME)
        print(f"session state        : {state.name}")
        print(f"latest turn          : {turn_path}")
        print(f"report.md present    : {adapter.path_exists(f'{turn_path}/report.md')}")
        print(f"workspace already hit: {adapter.path_exists(APPLIED_ARTIFACT)}")

        manager.resume(
            session_name=SESSION_NAME,
            orchestrator=orchestrator,
            require_approval=False,
            pipeline=False,
            message=None,
        )

        print(f"orchestrator calls   : {len(orchestrator.calls)}")
        for call in orchestrator.calls:
            print(f"  execute kwargs     : {sorted(call)}")
            print(f"  plan_path          : {call.get('plan_path')}")
            print(f"  pre-parsed plan    : {call.get('plan')}")

        assert state.name == "PENDING_PLAN", state
        assert len(orchestrator.calls) == 1, orchestrator.calls
        call = orchestrator.calls[0]
        assert "plan" not in call, (
            "bare resume passed a pre-parsed plan; the replay path was not taken"
        )
        assert str(call["plan_path"]).endswith("/01/plan.md"), call

    print()
    print("PASS: bare resume on PENDING_PLAN replays plan.md from action 1,")
    print("      with no record of the actions the killed run already applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
