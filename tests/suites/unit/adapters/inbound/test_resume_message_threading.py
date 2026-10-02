"""Unit tests: `--message/-m` and `--pipeline/-p` threading through the
resume CLI handlers.

Verifies that a message injected via `handle_resume_session(message=...)`
and the pipeline flag injected via `handle_resume_session(pipeline=...)`
reach the orchestrator resume chain (`_orchestrate_session_loop` ->
`orchestrator.resume`) as append-only keyword parameters, so the
lifecycle state machine can consume the reply without interactive
prompting and drive the pipeline stop semantics. The session loop is
driven to immediate termination by having the orchestrator double
return `(session_name, None)` — no module patching.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from teddy_executor.adapters.inbound.session_cli_handlers import (
    handle_resume_session,
)
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.ports.outbound.session_repository import ISessionRepository


class _ContainerStub:
    """Hand-rolled punq-compatible container double (no bare MagicMock)."""

    def __init__(self, mapping: dict[type, object]) -> None:
        self._mapping = mapping

    def resolve(self, service_type: type, **kwargs: object) -> object:
        service = self._mapping.get(service_type)
        if service is None:
            return Mock()
        return service


def _build_resume_harness() -> SimpleNamespace:
    """Builds the resume-handler harness with strictly bound doubles.

    Mirrors the established resume-handler test recipes: spec-bound mocks
    for every resolved service, inert defaults for the meta-sync and
    preflight surfaces, and an orchestrator double whose resume returns
    (session_name, None) so the shared turn loop breaks immediately.
    """
    session_manager = Mock(spec=ISessionManager)
    session_manager.get_latest_turn.return_value = ".teddy/sessions/test-session/01"
    session_manager.get_cumulative_cost.return_value = 0.0
    session_manager.resolve_session_from_path.return_value = "test-session"

    config_service = Mock(spec=IConfigService)
    config_service.get_setting.side_effect = lambda key, default="unknown": default
    config_service.get_config_path.return_value = ".teddy/config.yaml"

    repository = Mock(spec=ISessionRepository)
    repository.load_meta.return_value = {
        "agent_name": "assistant",
        "model": "test-model",
    }

    llm_client = Mock(spec=ILlmClient)
    llm_client.validate_config.return_value = []

    orchestrator = Mock(spec=IRunPlanUseCase)
    orchestrator.resume.return_value = ("test-session", None)

    loop_guard = Mock(spec=ISessionLoopGuard)
    loop_guard.should_continue.return_value = (True, None)

    report_formatter = Mock(spec=IMarkdownReportFormatter)
    report_formatter.format.return_value = "# Report"

    container = _ContainerStub(
        {
            IRunPlanUseCase: orchestrator,
            ISessionManager: session_manager,
            IConfigService: config_service,
            ISessionRepository: repository,
            ILlmClient: llm_client,
            ISessionLoopGuard: loop_guard,
            IMarkdownReportFormatter: report_formatter,
        }
    )
    return SimpleNamespace(
        container=container,
        orchestrator=orchestrator,
        session_manager=session_manager,
        loop_guard=loop_guard,
        report_formatter=report_formatter,
    )


class TestResumeMessageThreading:
    """Injected resume messages must reach the orchestrator resume chain."""

    def test_injected_message_reaches_orchestrator_resume(self) -> None:
        # Arrange
        h = _build_resume_harness()

        # Act
        handle_resume_session(
            container=h.container,
            path="test-session",
            interactive=False,
            no_copy=True,
            message="reply",
        )

        # Assert
        h.orchestrator.resume.assert_called_once_with(
            session_name="test-session",
            interactive=False,
            pipeline=False,
            message="reply",
        )

    def test_resume_without_message_passes_none(self) -> None:
        # Arrange
        h = _build_resume_harness()

        # Act
        handle_resume_session(
            container=h.container,
            path="test-session",
            interactive=False,
            no_copy=True,
        )

        # Assert: the default path threads message=None (no interactive
        # prompting difference; consumption semantics land in the Logic
        # deliverables).
        assert h.orchestrator.resume.call_count == 1
        assert h.orchestrator.resume.call_args.kwargs.get("message") is None

    def test_loop_clears_injected_message_after_first_iteration(self) -> None:
        """A report-bearing first iteration must consume the injected message.

        Regression guard: the shared session loop re-sent `message` into
        `orchestrator.resume` on EVERY iteration. A stale reply would
        re-plan later COMPLETE_TURNs; the loop must clear it to None
        after the first resume call so subsequent iterations resume
        without an injected message.
        """
        # Arrange: two-iteration loop — first resume yields a report, the
        # second terminates the session.
        h = _build_resume_harness()
        now = datetime.now(timezone.utc)
        report = ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS, start_time=now, end_time=now
            ),
            plan_title="Turn 1",
            action_logs=[],
        )
        h.orchestrator.resume.side_effect = [
            ("test-session", report),
            ("test-session", None),
        ]

        # Act
        handle_resume_session(
            container=h.container,
            path="test-session",
            interactive=False,
            no_copy=True,
            message="reply",
        )

        # Assert: the first call carries the injected reply; the follow-up
        # iteration must NOT re-plan with the stale message.
        first_call, second_call = h.orchestrator.resume.call_args_list
        assert first_call.kwargs["message"] == "reply"
        assert second_call.kwargs["message"] is None


class TestResumePipelineThreading:
    """The injected pipeline flag must reach the orchestrator resume chain."""

    def test_injected_pipeline_reaches_orchestrator_resume(self) -> None:
        # Arrange
        h = _build_resume_harness()

        # Act
        handle_resume_session(
            container=h.container,
            path="test-session",
            interactive=False,
            no_copy=True,
            pipeline=True,
        )

        # Assert: the pipeline flag threads through the handler into the
        # orchestrator resume chain as an append-only keyword parameter,
        # mirroring the established --message/-m threading precedent.
        h.orchestrator.resume.assert_called_once_with(
            session_name="test-session",
            interactive=False,
            pipeline=True,
            message=None,
        )
