import pytest
from unittest.mock import create_autospec
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.domain.models.execution_report import ExecutionReport
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.outbound.session_manager import (
    ISessionManager,
    SessionState,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_planner import SessionPlanner
from teddy_executor.core.services.session_replanner import SessionReplanner


@pytest.fixture
def manager(container):
    """Fixture to create a SessionLifecycleManager with mocked ports."""
    # We use register_mock to satisfy the SessionPorts dataclass with auto-specced mocks
    ports = SessionPorts(
        session_service=register_mock(container, ISessionManager),
        file_system_manager=register_mock(container, IFileSystemManager),
        report_formatter=register_mock(container, IMarkdownReportFormatter),
        user_interactor=register_mock(container, IUserInteractor),
        session_planner=register_mock(container, SessionPlanner),
        replanner=register_mock(container, SessionReplanner),
    )
    return SessionLifecycleManager(ports=ports)


def test_trigger_replan_accepts_plan_parameter(manager, container):
    # Arrange
    plan_path = "session/turn_1/plan.md"
    errors = ["Some error"]
    original_content = "plan content"
    mock_plan = register_mock(container, Plan)
    mock_plan.metadata = {}

    # Act & Assert
    # This should no longer fail with TypeError
    manager.trigger_replan(
        plan_path=plan_path,
        errors=errors,
        original_plan_content=original_content,
        plan=mock_plan,
    )


def test_trigger_replan_propagates_plan_to_finalize_turn(manager, container):
    # Arrange
    mock_plan = register_mock(container, Plan)
    mock_plan.metadata = {"pruned_context": "file_a.txt"}

    # Act
    manager.trigger_replan(
        plan_path="session/turn_1/plan.md",
        errors=["err"],
        original_plan_content="...",
        plan=mock_plan,
    )

    # Assert
    # Check that the plan metadata was processed and passed to the session service
    manager._session_service.transition_to_next_turn.assert_called_once()
    args, kwargs = manager._session_service.transition_to_next_turn.call_args
    assert kwargs.get("pruned_paths") == ["file_a.txt"], (
        "Pruned paths from plan were not propagated"
    )


class TestTriggerReplanIsSession:
    """Tests for the is_session parameter in trigger_replan."""

    def test_default_is_session_false(self, manager, container) -> None:
        """When is_session is not provided, it must default to False."""
        manager.trigger_replan(
            plan_path="session/turn_1/plan.md",
            errors=["Error 1"],
            original_plan_content="# Plan",
        )
        manager._replanner.build_failure_report.assert_called_once()
        call_kwargs = manager._replanner.build_failure_report.call_args.kwargs
        assert "is_session" in call_kwargs
        assert call_kwargs["is_session"] is False

    @pytest.mark.parametrize("is_session", [True, False])
    def test_is_session_forwarded(self, manager, container, is_session: bool) -> None:
        """is_session must be forwarded to build_failure_report."""
        manager.trigger_replan(
            plan_path="session/turn_1/plan.md",
            errors=["Error 1"],
            original_plan_content="# Plan",
            is_session=is_session,
        )
        manager._replanner.build_failure_report.assert_called_once()
        call_kwargs = manager._replanner.build_failure_report.call_args.kwargs
        assert call_kwargs["is_session"] == is_session


def test_resume_returns_tuple_with_session_name_and_report(manager):
    """resume() must return (actual_session_name, report) tuple after migration."""
    # Configure session state: first call returns COMPLETE_TURN (initial session),
    # second call returns PENDING_PLAN (continuation session)
    manager._session_service.get_session_state.side_effect = [
        (SessionState.COMPLETE_TURN, "/root/my-session/turns/99"),
        (SessionState.PENDING_PLAN, "/root/my-session-2/turns/01"),
    ]

    # Configure transition_to_next_turn to return the continuation turn dir
    manager._session_service.transition_to_next_turn.return_value = (
        "/root/my-session-2/turns/01"
    )

    # Configure trigger_new_plan to return the new session name
    manager._session_planner.trigger_new_plan.return_value = "my-session-2"

    # Configure orchestrator.execute to return a report
    mock_report = create_autospec(ExecutionReport, instance=True)
    mock_orchestrator = create_autospec(IRunPlanUseCase, instance=True)
    mock_orchestrator.execute.return_value = mock_report

    result = manager.resume(
        session_name="my-session",
        orchestrator=mock_orchestrator,
        interactive=False,
    )

    # Assert result is a tuple (session_name, report)
    assert isinstance(result, tuple), f"Expected tuple, got {type(result)}"
    assert len(result) == 2, f"Expected 2 elements, got {len(result)}"
    actual_session_name, report = result
    assert actual_session_name == "my-session-2", (
        f"Expected session name 'my-session-2', got {actual_session_name}"
    )
    assert report is mock_report, "Report should be the one returned by orchestrator"
