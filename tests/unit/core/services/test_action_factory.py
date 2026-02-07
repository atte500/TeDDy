from unittest.mock import Mock
import pytest
import punq

from teddy_executor.core.ports.outbound import IShellExecutor, IFileSystemManager
from teddy_executor.core.services.action_factory import ActionFactory

# --- Fixtures ---


@pytest.fixture
def mock_shell_executor() -> Mock:
    return Mock(spec=IShellExecutor)


@pytest.fixture
def mock_file_system_manager() -> Mock:
    return Mock(spec=IFileSystemManager)


@pytest.fixture
def container(
    mock_shell_executor: Mock, mock_file_system_manager: Mock
) -> punq.Container:
    """A pytest fixture to provide a pre-configured mock DI container."""
    mock_container = punq.Container()
    mock_container.register(IShellExecutor, instance=mock_shell_executor)
    mock_container.register(IFileSystemManager, instance=mock_file_system_manager)
    return mock_container


@pytest.fixture
def factory(container: punq.Container) -> ActionFactory:
    """Provides an ActionFactory instance with a mocked container."""
    return ActionFactory(container=container)


# --- Test Cases ---


def test_create_action_successfully_resolves_handler(
    factory: ActionFactory, mock_shell_executor: Mock
):
    """
    Given a known action type ('execute'),
    When create_action is called,
    Then it should resolve and return the correct handler from the container.
    """
    # Arrange
    action_type = "execute"

    # Act
    action_handler = factory.create_action(action_type)

    # Assert
    assert action_handler is mock_shell_executor


def test_create_action_raises_error_for_unknown_type(factory: ActionFactory):
    """
    Given an unknown action type,
    When create_action is called,
    Then it should raise a ValueError.
    """
    # Arrange
    action_type = "non_existent_action"

    # Act & Assert
    with pytest.raises(ValueError, match="Unknown action type: 'non_existent_action'"):
        factory.create_action(action_type)


def test_create_action_for_conclude_returns_handler(factory: ActionFactory):
    """
    Given the 'CONCLUDE' action type,
    When create_action is called,
    Then it should return a ConcludeAction handler.
    """
    # Arrange
    from teddy_executor.core.services.action_factory import ConcludeAction

    action_type = "CONCLUDE"

    # Act
    action_handler = factory.create_action(action_type)

    # Assert
    assert isinstance(action_handler, ConcludeAction)
