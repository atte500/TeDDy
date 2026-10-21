"""MRE: a structural parse failure drops the plan H1 from the report title.

The probe drives the sandbox replica of the faulty seam so the proposed fix is
proven without touching production code:
SessionOrchestrator._prepare_plan_parsing -> SessionLifecycleManager.trigger_replan
-> SessionReplanner.build_failure_report -> MarkdownReportFormatter.

Only outbound ports are faked. The probe captures the exact bytes that
finalize_turn writes to report.md.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_replanner import SessionReplanner

from replica_session_orchestrator import SessionOrchestrator

PLAN_PATH = ".teddy/sessions/demo/01/plan.md"
EXPECTED_TITLE = "A Perfectly Valid Title"

# Built at runtime so the file never contains a literal six-tilde line, which
# would collide with any fence used to embed this script.
FENCE = "~" * 6

# Valid H1 plus a complete metadata list and rationale, but no action section.
# The parser extracts the H1, then validate_plan_structure raises on the
# missing H2 Action Plan heading.
PLAN_CONTENT = f"""# A Perfectly Valid Title
- **Agent:** Debugger
- **Plan Type:** Discovery

## Rationale
{FENCE}
The plan carries a parseable H1 but no action section.
{FENCE}
"""


class RecordingFileSystem:
    """In-memory file system port that records writes."""

    def __init__(self) -> None:
        self.writes: dict[str, str] = {}

    def path_exists(self, path) -> bool:
        return str(path) in self.writes

    def read_file(self, path) -> str:
        return self.writes.get(str(path), "")

    def write_file(self, path, content) -> None:
        self.writes[str(path)] = str(content)

    def create_directory(self, path) -> None:
        return None

    def open_file_for_append(self, path):
        raise AssertionError("open_file_for_append must not be called by this path")


class RecordingInteractor:
    """User interactor port that records messages."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def display_message(self, message) -> None:
        self.messages.append(str(message))


class FakeSessionService:
    """Session manager port with deterministic turn transitions."""

    def to_root_relative(self, turn_dir, filename) -> str:
        return f"{turn_dir}/{filename}"

    def transition_to_next_turn(self, **kwargs) -> str:
        return ".teddy/sessions/demo/02"

    def get_session_state(self, session_name):
        raise AssertionError("get_session_state must not be called by this path")


class FakeSessionPlanner:
    """Session planner port placeholder."""


class FakePlanningService:
    """Planning service port that records replan requests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def generate_plan(self, user_message, turn_dir) -> None:
        self.calls.append((str(user_message), str(turn_dir)))


def build_lifecycle_manager(fs, interactor, planning_service) -> SessionLifecycleManager:
    replanner = SessionReplanner(
        file_system_manager=fs,
        planning_service=planning_service,
    )
    ports = SessionPorts(
        session_service=FakeSessionService(),
        file_system_manager=fs,
        report_formatter=MarkdownReportFormatter(),
        user_interactor=interactor,
        session_planner=FakeSessionPlanner(),
        replanner=replanner,
        plan_parser=MarkdownPlanParser(),
    )
    return SessionLifecycleManager(ports=ports)


def build_orchestrator(fs, manager) -> SessionOrchestrator:
    """Isolate the parsing seam without the full thirteen-port constructor."""
    orchestrator = object.__new__(SessionOrchestrator)
    orchestrator._plan_parser = MarkdownPlanParser()
    orchestrator._file_system_manager = fs
    orchestrator._lifecycle_manager = manager
    orchestrator._replanner = manager._replanner
    orchestrator._user_interactor = manager._user_interactor
    return orchestrator


def main() -> int:
    fs = RecordingFileSystem()
    interactor = RecordingInteractor()
    planning_service = FakePlanningService()
    manager = build_lifecycle_manager(fs, interactor, planning_service)
    orchestrator = build_orchestrator(fs, manager)

    report = orchestrator._prepare_plan_parsing(
        plan=None,
        plan_content=PLAN_CONTENT,
        plan_path=PLAN_PATH,
        is_session=True,
    )

    report_path = f"{Path(PLAN_PATH).parent}/report.md"
    rendered = fs.writes.get(report_path, "")

    print("=== returned report title ===")
    print(repr(getattr(report, "plan_title", None)))
    print("=== captured report path ===")
    print(report_path)
    print("=== rendered report header ===")
    print(rendered.splitlines()[0] if rendered else "<no report written>")
    print("=== recorded validation errors ===")
    for message in getattr(report, "validation_result", []) or []:
        print(message.splitlines()[0])
    print("=== user-facing notices ===")
    for message in interactor.messages:
        print(message)
    print("=== replan handoff ===")
    print(planning_service.calls)

    actual = getattr(report, "plan_title", None)
    header_ok = rendered.startswith(f"# Execution Report: {EXPECTED_TITLE}")
    if actual == EXPECTED_TITLE and header_ok:
        print(f"\nRESULT: PASS - the report title carries the parsed H1 {EXPECTED_TITLE!r}.")
        return 0

    print(
        f"\nRESULT: FAIL - expected title {EXPECTED_TITLE!r}, "
        f"got {actual!r}; header match: {header_ok}."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())