"""Unit tests: pipeline no-message stop-again in `_consume_awaiting_reply`.

Case 2 of the locked consumption design (user-approved): `teddy resume -p`
WITHOUT an injected message on an awaiting-reply turn (pipeline MESSAGE
turn stopped before finalization) must re-trigger the agent's MESSAGE —
re-printed via the interactor — and exit again WITHOUT finalizing or
transitioning: the `awaiting_reply` flag is PRESERVED (a later
`resume -p -m` can inject the reply), no turn 02 is created, no report.md
is written, and the synthesized message-turn report is returned so the
CLI pipeline break fires.
"""

from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock, create_autospec

import pytest
import typer

from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.plan import ActionData, Plan
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
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
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner
from tests.harness.setup.mocking import register_mock

AWAITING_TURN = ".teddy/sessions/20260417_120000-feature/01"
AGENT_MESSAGE = "Hi there! How are you doing today?"
PLAN_CONTENT = "# Greet User and Check In\n\n## Action Plan\n\n### MESSAGE\n..."
META_CONTENT = "agent_name: assistant\nturn_cost: 0.25\n"
FORMATTED_REPORT = (
    "# Execution Report: Greet User and Check In\n\n## Action Log\n\n"
    "### `MESSAGE`\n- **User Reply:**\n```\n" + AGENT_MESSAGE + "\n```\n"
)


@pytest.fixture
def manager(container):
    """SessionLifecycleManager with auto-specced port doubles plus the
    consumption doubles riding the Seam's optional ports."""
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
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
        plan_parser=plan_parser,
        time_service=time_service,
        report_assembler=ExecutionReportAssembler(),
    )
    return SessionLifecycleManager(ports=ports)


def _orchestrator_double():
    return create_autospec(IRunPlanUseCase, instance=True)


def _arrange_awaiting_reply(manager) -> None:
    """Classification: plan.md present, report.md absent (PENDING_PLAN).

    The awaiting turn's meta carries the flag; the interrupted plan's
    markdown is read via path-keyed read_file (the synthesis parses
    plan.md, never the meta yaml). The stop-again flow calls
    get_session_state exactly ONCE (the resume-top classification) — no
    post-planning re-resolution happens because no turn is planned.
    """
    manager._session_service.get_session_state.side_effect = [
        (SessionState.PENDING_PLAN, AWAITING_TURN)
    ]
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
    manager._report_formatter.format.return_value = FORMATTED_REPORT


class TestPipelineNoMessageStopAgain:
    """`resume -p` without a message re-triggers the MESSAGE and exits again."""

    @pytest.fixture(autouse=True)
    def _capture_message_rendering(self, monkeypatch):
        """Capture the shared MESSAGE-rendering helpers' `typer.secho` output."""
        self.secho_calls = []

        def _fake_secho(text, **kwargs):
            self.secho_calls.append((text, kwargs))

        monkeypatch.setattr(
            "teddy_executor.core.services.session_orchestrator.typer.secho",
            _fake_secho,
        )

    def test_stop_again_reprints_message_and_preserves_awaiting_state(
        self, manager
    ) -> None:
        # Arrange
        _arrange_awaiting_reply(manager)
        orchestrator = _orchestrator_double()

        # Act
        result = manager.resume(
            session_name="feature",
            orchestrator=orchestrator,
            interactive=False,
            pipeline=True,
            message=None,
        )

        # Assert: the agent's MESSAGE is re-printed through the shared
        # MESSAGE-rendering path (`_print_header_bar` + the
        # `_print_message_from_teddy` framing) — NOT the bare, un-styled
        # `display_message` channel — so the stop-again presentation matches
        # the pipeline-start presentation (Bug 54 / defect 4a).
        manager._user_interactor.display_message.assert_not_called()
        rendered = [call[0] for call in self.secho_calls]
        assert "Greet User and Check In" in rendered, rendered
        frame_calls = [
            call for call in self.secho_calls if call[0] == "--- MESSAGE from TeDDy ---"
        ]
        assert len(frame_calls) == 1, rendered
        assert frame_calls[0][1].get("fg") == typer.colors.CYAN, frame_calls
        assert AGENT_MESSAGE in rendered, rendered
        # The status header precedes the framing, which precedes the body.
        assert rendered.index("Greet User and Check In") < rendered.index(
            "--- MESSAGE from TeDDy ---"
        )
        assert rendered.index("--- MESSAGE from TeDDy ---") < rendered.index(
            AGENT_MESSAGE
        )
        # Assert: no interactive prompt on the pipeline path.
        manager._user_interactor.ask_question.assert_not_called()
        # Assert: the synthesized message-turn report is returned so the
        # CLI pipeline break fires.
        assert result[0] == "feature"
        assert result[1] is not None
        message_logs = [
            log for log in result[1].action_logs if log.action_type == "MESSAGE"
        ]
        assert len(message_logs) == 1
        # The stop-again path carries NO user reply: the agent's own text is
        # preserved in `params["content"]` (the re-print source), while
        # `details` stays empty so the template never mislabels the agent's
        # message as the user's reply.
        assert message_logs[0].params["content"] == AGENT_MESSAGE
        assert message_logs[0].details is None
        # Assert: the interrupted plan was parsed for the synthesis.
        manager._plan_parser.parse.assert_called_once()
        # Assert: the awaiting_reply flag is PRESERVED — no meta mutation,
        # so a later `resume -p -m` can inject the reply.
        manager._session_service.save_turn_meta.assert_not_called()
        # Assert: NO finalization and NO transition — the report is never
        # rendered or persisted, and turn 02 is never created.
        manager._report_formatter.format.assert_not_called()
        manager._file_system_manager.write_file.assert_not_called()
        manager._session_service.transition_to_next_turn.assert_not_called()
        # Assert: no planning/execution chain ran.
        manager._session_planner.trigger_new_plan.assert_not_called()
        orchestrator.execute.assert_not_called()
