"""Tests for confirm_and_dispatch MESSAGE action return value."""

import pytest
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.domain.models.plan import ActionData
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
)


@pytest.fixture
def executor(container):
    """Create an ActionExecutor with mocked dependencies."""
    register_mock(container, ActionDispatcher)
    register_mock(container, IUserInteractor)
    register_mock(container, IFileSystemManager)
    register_mock(container, EditSimulator)
    register_mock(container, IConfigService)
    return container.resolve(ActionExecutor)


def test_confirm_and_dispatch_returns_user_message_for_message_action(executor):
    """
    For MESSAGE actions, confirm_and_dispatch should return the user's typed
    message as the second return value, not the empty reason string.
    """
    # Arrange: create a MESSAGE action
    message_action = ActionData(
        type="MESSAGE",
        params={"prompt": "What do you think?", "content": "Hello"},
        description="Message to user",
    )

    # Set up the mock dispatcher to return an ActionLog with the user's reply in details
    executor._action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="MESSAGE",
        params=message_action.params.copy(),
        details="I think this is a great idea!",
    )

    # Act: dispatch the MESSAGE action
    action_log, user_message = executor.confirm_and_dispatch(
        message_action, interactive=False, total_actions=1
    )

    # Assert: the second return value should be the user's typed message
    assert action_log.status == ActionStatus.SUCCESS
    assert user_message == "I think this is a great idea!", (
        f"Expected user message 'I think this is a great idea!', got '{user_message}'"
    )


def test_confirm_and_dispatch_returns_empty_for_non_message_action(executor):
    """
    For non-MESSAGE actions, confirm_and_dispatch should return the reason
    (empty string when not interactive) as the second return value.
    """
    # Arrange: create a non-MESSAGE action (e.g., READ)
    read_action = ActionData(
        type="READ",
        params={"path": "test.txt"},
        description="Read a file",
    )

    # Set up the mock dispatcher to return a success ActionLog
    executor._action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="READ",
        params=read_action.params.copy(),
        details="file content",
    )

    # Act: dispatch the READ action
    action_log, second_value = executor.confirm_and_dispatch(
        read_action, interactive=False, total_actions=1
    )

    # Assert: the second return value should be empty string (reason)
    assert action_log.status == ActionStatus.SUCCESS
    assert second_value == "", (
        f"Expected empty string for non-MESSAGE action, got '{second_value}'"
    )
