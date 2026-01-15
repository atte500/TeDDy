import pytest
import punq

from teddy_executor.core.ports.outbound import IShellExecutor, IFileSystemManager
from teddy_executor.core.services.action_factory import ActionFactory

# --- Test Doubles ---


class MockShellExecutor:
    def execute(self, **kwargs):
        pass


class MockFileSystemManager:
    def create_file(self, **kwargs):
        pass


# --- Test Cases ---


@pytest.fixture
def container() -> punq.Container:
    """A pytest fixture to provide a pre-configured mock DI container."""
    mock_container = punq.Container()
    mock_container.register(IShellExecutor, MockShellExecutor)
    mock_container.register(IFileSystemManager, MockFileSystemManager)
    return mock_container


def test_create_action_successfully_resolves_handler(container: punq.Container):
    """
    Given a known action type ('execute'),
    When create_action is called,
    Then it should resolve and return the correct handler from the container.
    """
    # Arrange
    factory = ActionFactory(container=container)
    action_type = "execute"

    # Act
    action_handler = factory.create_action(action_type)

    # Assert
    assert isinstance(action_handler, MockShellExecutor)


def test_create_action_raises_error_for_unknown_type(container: punq.Container):
    """
    Given an unknown action type,
    When create_action is called,
    Then it should raise a ValueError.
    """
    # Arrange
    factory = ActionFactory(container=container)
    action_type = "non_existent_action"

    # Act & Assert
    with pytest.raises(ValueError, match="Unknown action type: 'non_existent_action'"):
        factory.create_action(action_type)
