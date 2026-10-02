"""Unit tests: reply-driven finalization in `_consume_awaiting_reply`.

The locked consumption design (user-approved): a reply on an
awaiting-reply turn (pipeline MESSAGE turn stopped before
finalization) must FINALIZE the interrupted turn — synthesizing the
standard message-turn report from its plan via the Constructor-Injected
plan parser and time service, writing `report.md` through
`finalize_turn` (NO `## User Request` section: the consumption path
never appends — the interrupted turn has no prior report) — then clear
the `awaiting_reply` flag and plan+execute the next turn with the
reply. This applies across ALL resume modes (pipeline or not).
"""

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import Mock, create_autospec

import pytest

from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.domain.models.report_assembly_data import ReportAssemblyData
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.execution_report_assembler import (
    IExecutionReportAssembler,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.time_service import ITimeService
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.execution_report_assembler import (
    ExecutionReportAssembler,
)
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock

AWAITING_TURN = ".teddy/sessions/20260417_120000-feature/01"
NEXT_TURN = ".teddy/sessions/20260417_120000-feature/02"
REPLY = "I am great, tell me a joke"
AGENT_MESSAGE = "Hi there! How are you doing today?"
PLAN_CONTENT = "# Greet User and Check In\n\n## Action Plan\n\n### MESSAGE\n..."
META_CONTENT = "agent_name: assistant\nturn_cost: 0.25\n"
FORMATTED_REPORT = (
    "# Execution Report: Greet User and Check In\n\n## Action Log\n\n"
    "### `MESSAGE`\n- **User Reply:**\n```\n" + AGENT_MESSAGE + "\n```\n"
)


def _build_manager(container, report_formatter, report_assembler=None):
    """Assemble a SessionLifecycleManager around a caller-supplied report
    formatter — a spec-bound double for field-level assertions, or the REAL
    MarkdownReportFormatter for rendering regressions.

    The optional `report_assembler` seam is injected only when a test
    exercises it, so the surrounding synthesis tests stay unchanged.
    """
    plan_parser = cast(IPlanParser, Mock(spec=IPlanParser))
    plan_parser.parse.return_value = Plan(
        title="Greet User and Check In",
        rationale="Communication turn",
        actions=[
            ActionData(
                type="MESSAGE",
                # Mirrors the production parser reality: parse_message_action
                # writes params={"content": content} (action_parser_complex).
                params={"content": AGENT_MESSAGE},
                description="Message to user",
            )
        ],
    )
    time_service = cast(ITimeService, Mock(spec=ITimeService))
    time_service.now.return_value = datetime(2026, 10, 2, 12, 0, 0)
    time_service.now_utc.return_value = datetime(
        2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc
    )
    # The assembler seam is ALWAYS supplied — a caller-supplied double when a
    # test exercises it, otherwise the REAL assembler — so the synthesis
    # delegation resolves under every construction.
    seam_kwargs: dict[str, Any] = {
        "report_assembler": (
            report_assembler
            if report_assembler is not None
            else ExecutionReportAssembler()
        ),
    }
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=report_formatter,
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        plan_parser=plan_parser,
        time_service=time_service,
        **seam_kwargs,
    )
    return SessionLifecycleManager(ports=ports)


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles plus the
    consumption doubles riding the Seam's optional ports."""
    return _build_manager(container, register_mock(container, IMarkdownReportFormatter))


def _orchestrator_with_report():
    orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    orchestrator.execute.return_value = create_autospec(ExecutionReport, instance=True)
    return orchestrator


def _arrange_awaiting_reply(manager) -> None:
    """Classification: plan.md present, report.md absent (PENDING_PLAN).

    The awaiting turn's meta carries the flag; the interrupted plan's
    markdown is read via path-keyed read_file (finalize_turn's meta read
    must see the meta yaml, not the plan markdown).
    """
    manager._session_service.get_session_state.side_effect = [
        (SessionState.PENDING_PLAN, AWAITING_TURN),
        (SessionState.PENDING_PLAN, NEXT_TURN),
    ]
    manager._session_service.transition_to_next_turn.return_value = NEXT_TURN
    manager._session_service.load_turn_meta.return_value = {
        "agent_name": "assistant",
        "awaiting_reply": True,
    }
    manager._session_service.to_root_relative.side_effect = lambda turn_dir, filename: (
        f"{turn_dir}/{filename}"
    )
    manager._file_system_manager.path_exists.side_effect = lambda path: str(
        path
    ).endswith("meta.yaml")
    manager._file_system_manager.read_file.side_effect = lambda path: (
        PLAN_CONTENT if str(path).endswith("plan.md") else META_CONTENT
    )
    manager._session_planner.trigger_new_plan.return_value = ("feature", None)


def test_reply_finalizes_awaiting_turn_then_plans_next_turn(manager) -> None:
    # Arrange
    _arrange_awaiting_reply(manager)
    manager._report_formatter.format.return_value = FORMATTED_REPORT
    orchestrator = _orchestrator_with_report()

    # Act
    result = manager.resume(
        session_name="feature",
        orchestrator=orchestrator,
        interactive=False,
        message=REPLY,
    )

    # Assert: the interrupted plan was parsed for the synthesis.
    manager._plan_parser.parse.assert_called_once()
    # Assert: the synthesized report carries the MESSAGE log in the canonical
    # shape — the USER's reply in `details` (rendered under `- **User Reply:**`)
    # and the agent's own text preserved in `params["content"]`.
    manager._report_formatter.format.assert_called_once()
    synthesized = manager._report_formatter.format.call_args.args[0]
    message_logs = [
        log for log in synthesized.action_logs if log.action_type == "MESSAGE"
    ]
    assert len(message_logs) == 1
    assert message_logs[0].details == REPLY
    assert message_logs[0].params["content"] == AGENT_MESSAGE
    # Assert: the interrupted turn is FINALIZED — the standard message-turn
    # report lands at 01/report.md with NO ## User Request section (locked
    # design: the append applies only when a prior report already exists).
    manager._file_system_manager.write_file.assert_called_once()
    written_path = str(manager._file_system_manager.write_file.call_args.args[0])
    assert written_path.endswith("01/report.md"), written_path
    written_content = manager._file_system_manager.write_file.call_args.args[1]
    assert written_content == FORMATTED_REPORT
    assert "## User Request" not in written_content
    # Assert: the awaiting_reply flag is stripped from the turn meta.
    save_call = manager._session_service.save_turn_meta.call_args
    assert save_call is not None
    assert "awaiting_reply" not in save_call.args[1]
    # Assert: the transition carries the synthesized report (finalize_turn).
    transition_call = manager._session_service.transition_to_next_turn.call_args
    assert transition_call.kwargs.get("execution_report") is synthesized
    # Assert: turn 02 is planned from the injected reply and executed —
    # no interactive prompt on the injected-reply path.
    manager._user_interactor.ask_question.assert_not_called()
    manager._session_planner.trigger_new_plan.assert_called_once_with(
        NEXT_TURN, message=REPLY
    )
    executed_plan = orchestrator.execute.call_args.kwargs["plan_path"]
    assert NEXT_TURN in executed_plan
    assert result[0] == "feature"


def test_finalized_report_renders_user_reply_not_agent_message(container) -> None:
    """Regression (Bug 54 / defect 4b): the finalized message-turn report
    must render the USER's injected reply under `- **User Reply:**` and must
    NEVER mislabel the agent's own message as the user's reply.

    Rendered through the REAL MarkdownReportFormatter so the assertion is
    bound to the actual template contract — a spec-bound double would hide
    the exact misrouting this fix removes.
    """
    manager = _build_manager(container, MarkdownReportFormatter())
    _arrange_awaiting_reply(manager)
    orchestrator = _orchestrator_with_report()

    # Act
    manager.resume(
        session_name="feature",
        orchestrator=orchestrator,
        interactive=False,
        message=REPLY,
    )

    # Assert: the finalized report renders the USER's reply under the
    # `- **User Reply:**` header and NEVER the agent's own message.
    written_path = str(manager._file_system_manager.write_file.call_args.args[0])
    assert written_path.endswith("01/report.md"), written_path
    rendered = manager._file_system_manager.write_file.call_args.args[1]
    assert "**User Reply:**" in rendered
    user_reply_section = rendered[rendered.index("**User Reply:**") :]
    assert REPLY in user_reply_section
    assert AGENT_MESSAGE not in user_reply_section


def test_synthesis_routes_through_report_assembler(container) -> None:
    """Refactor (Bug 54 / hand-rolled synthesis consolidation): the
    message-turn report synthesis delegates to the injected
    ExecutionReportAssembler so the finalized shape cannot drift from the
    standard template contract, while preserving the 4b semantics — the USER
    reply in the MESSAGE log's `details`, the agent text in `params`."""
    assembler = cast(IExecutionReportAssembler, Mock(spec=IExecutionReportAssembler))
    sentinel = create_autospec(ExecutionReport, instance=True)
    assembler.assemble.return_value = sentinel
    manager = _build_manager(
        container,
        register_mock(container, IMarkdownReportFormatter),
        report_assembler=assembler,
    )
    _arrange_awaiting_reply(manager)
    orchestrator = _orchestrator_with_report()

    # Act
    result = manager.resume(
        session_name="feature",
        orchestrator=orchestrator,
        interactive=False,
        message=REPLY,
    )

    # Assert: the synthesis delegated to the assembler with the canonical DTO.
    assembler.assemble.assert_called_once()
    data = assembler.assemble.call_args.args[0]
    assert isinstance(data, ReportAssemblyData)
    assert data.plan.title == "Greet User and Check In"
    assert len(data.action_logs) == 1
    assert data.action_logs[0].action_type == "MESSAGE"
    # 4b semantics preserved: USER reply in `details`, agent text in `params`.
    assert data.action_logs[0].details == REPLY
    assert data.action_logs[0].params["content"] == AGENT_MESSAGE
    # No `## User Request` section on the consumption path.
    assert data.message is None
    # The injected time service still feeds the DTO's start timestamp (DI purity).
    assert data.start_time == datetime(2026, 10, 2, 12, 0, 0, tzinfo=timezone.utc)
    # The synthesized report IS the assembler's output (not hand-rolled).
    transition_call = manager._session_service.transition_to_next_turn.call_args
    assert transition_call.kwargs.get("execution_report") is sentinel
    assert result[0] == "feature"
