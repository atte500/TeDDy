import pytest
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.domain.models.planning_ports import SessionPorts
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
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
