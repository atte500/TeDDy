"""Regression: `resume -m` must durably persist the injected message.

Two coupled failure modes of the resume `-m` state machine are pinned here:

1. Pre-first-plan (`EMPTY` / turn 01): the injected message must be appended
   to the session's durable `initial_request.md` (seeded into
   `session.context` at creation), not silently dropped by
   `_append_message_to_previous_turn` (which no-ops for turn 01 because no
   predecessor report exists).
2. Mid-session (`EMPTY` / turn >01): the message appends a `## User Request`
   section to the predecessor turn's report, and that augmented turn must
   then be re-evaluated for preservation so it is admitted to the
   prune-exempt, session-scoped `session.context` (its own preservation
   decision already ran at finalize, before the append).

Both tests drive the real `SessionLifecycleManager` and assert on observable
file effects (`initial_request.md` / `session.context` contents), never on
internal call sequences.
"""

from pathlib import Path
from typing import cast
from unittest.mock import Mock, create_autospec

from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.ports.inbound.init import IInitUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.services.session_repository import SessionRepository
from teddy_executor.core.services.session_service import SessionService

SESSION_NAME = "20261005_090000-add-login"
SESSION_ROOT = f".teddy/sessions/{SESSION_NAME}"
TURN01 = f"{SESSION_ROOT}/01"
TURN02 = f"{SESSION_ROOT}/02"
INITIAL_REQUEST = f"{SESSION_ROOT}/initial_request.md"
SESSION_CONTEXT = f"{SESSION_ROOT}/session.context"
MESSAGE = "Also add OAuth support"


class InMemoryFileSystem:
    """Minimal dict-backed IFileSystemManager fake.

    Implements only the surface the resume EMPTY path and the real
    `SessionService` preservation pipeline touch: existence checks, reads,
    writes, and immediate-child directory listing (used by `get_latest_turn`).
    """

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self._dirs: set[str] = set()

    def _register_parents(self, path: str) -> None:
        parts = Path(path).parts
        for i in range(1, len(parts)):
            self._dirs.add("/".join(parts[:i]))

    def path_exists(self, path: str) -> bool:
        p = str(path)
        return p in self.files or p in self._dirs

    def read_file(self, path: str) -> str:
        return self.files[str(path)]

    def write_file(self, path: str, content: str) -> None:
        self.files[str(path)] = content
        self._register_parents(str(path))

    def list_directory(self, path: str) -> list[str]:
        prefix = str(path).rstrip("/") + "/"
        children: set[str] = set()
        for key in list(self.files) + list(self._dirs):
            if key.startswith(prefix):
                rest = key[len(prefix) :]
                if rest:
                    children.add(rest.split("/")[0])
        return sorted(children)


def _build_manager(
    fs, session_service, planner, orchestrator
) -> SessionLifecycleManager:
    ports = SessionPorts(
        session_service=session_service,
        file_system_manager=fs,
        report_formatter=Mock(spec=IMarkdownReportFormatter),
        user_interactor=Mock(spec=IUserInteractor),
        session_planner=planner,
        replanner=Mock(spec=SessionReplanner),
        plan_parser=Mock(spec=IPlanParser),
        time_service=Mock(spec=ITimeService),
        report_assembler=Mock(spec=IExecutionReportAssembler),
    )
    manager = SessionLifecycleManager(ports=ports)
    manager.tee_active = True  # bypass Tee installation
    return manager


class TestResumeMessageBeforeFirstPlan:
    """EMPTY / turn 01: the injected message augments initial_request.md."""

    def test_message_is_appended_to_initial_request(self) -> None:
        fs = InMemoryFileSystem()
        fs.write_file(INITIAL_REQUEST, "Build a login page")

        session_service = create_autospec(ISessionManager, instance=True)
        session_service.get_session_state.return_value = (SessionState.EMPTY, TURN01)
        session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
            f"{Path(turn_dir).as_posix()}/{filename}"
        )

        planner = Mock(spec=SessionPlanner)
        planner.trigger_new_plan.return_value = (SESSION_NAME, None)
        orchestrator = create_autospec(IRunPlanUseCase, instance=True)

        manager = _build_manager(fs, session_service, planner, orchestrator)

        manager.resume(
            session_name=SESSION_NAME,
            orchestrator=orchestrator,
            interactive=False,
            message=MESSAGE,
        )

        content = fs.files[INITIAL_REQUEST]
        assert "Build a login page" in content
        assert MESSAGE in content
        # The appended request must be plain text, NOT a `## Additional
        # Request` heading + smart-fenced codeblock: the initial request and
        # the injected message sit on adjacent lines.
        assert "## Additional Request" not in content
        assert content == f"Build a login page\n{MESSAGE}\n"


class TestResumeMessageMidSessionPreserved:
    """EMPTY / turn >01: the augmented predecessor turn enters session.context."""

    def _build(self):
        fs = InMemoryFileSystem()
        fs.write_file(INITIAL_REQUEST, "Build a login page")
        fs.write_file(SESSION_CONTEXT, INITIAL_REQUEST)
        fs.write_file(
            f"{TURN01}/plan.md",
            "# Plan: Build a login page\n\n## Action\n"
            "### `CREATE`: [login.py](/src/login.py)\n",
        )
        fs.write_file(
            f"{TURN01}/report.md",
            "# Execution Report: Build a login page\n- **Overall Status:** SUCCESS\n",
        )
        fs.write_file(f"{TURN02}/turn.context", f"{TURN01}/plan.md\n{TURN01}/report.md")

        config_service = Mock(spec=IConfigService)
        config_service.get_setting.return_value = True

        session_service = SessionService(
            file_system_manager=cast(IFileSystemManager, fs),
            repository=SessionRepository(cast(IFileSystemManager, fs)),
            time_service=Mock(spec=ITimeService),
            prompt_manager=Mock(spec=IPromptManager),
            init_service=Mock(spec=IInitUseCase),
            config_service=config_service,
        )

        planner = Mock(spec=SessionPlanner)
        planner.trigger_new_plan.return_value = (SESSION_NAME, None)
        orchestrator = create_autospec(IRunPlanUseCase, instance=True)

        manager = _build_manager(fs, session_service, planner, orchestrator)
        return manager, fs, orchestrator

    def test_augmented_turn_is_preserved_into_session_context(self) -> None:
        manager, fs, orchestrator = self._build()

        manager.resume(
            session_name=SESSION_NAME,
            orchestrator=orchestrator,
            interactive=False,
            message=MESSAGE,
        )

        # The injected message is recorded on the predecessor turn's report...
        assert "## User Request" in fs.files[f"{TURN01}/report.md"]
        # ...and the augmented turn is promoted into the prune-exempt,
        # session-scoped context so it survives turn-scope pruning.
        session_context = fs.files[SESSION_CONTEXT]
        assert f"{TURN01}/plan.md" in session_context
        assert f"{TURN01}/report.md" in session_context

    def test_no_message_leaves_session_context_untouched(self) -> None:
        manager, fs, orchestrator = self._build()

        manager.resume(
            session_name=SESSION_NAME,
            orchestrator=orchestrator,
            interactive=False,
        )

        # Control: a bare resume must not promote the predecessor turn.
        assert fs.files[SESSION_CONTEXT] == INITIAL_REQUEST
        assert "## User Request" not in fs.files[f"{TURN01}/report.md"]
