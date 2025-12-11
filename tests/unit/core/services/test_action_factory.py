import pytest

from teddy.core.domain.models import ExecuteAction, CreateFileAction
from teddy.core.services.action_factory import ActionFactory


class TestActionFactory:
    def test_create_execute_action(self):
        """
        Tests that the factory can create a valid ExecuteAction.
        """
        # Arrange
        raw_action = {
            "action": "execute",
            "params": {"command": "ls -l"},
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, ExecuteAction)
        assert action.command == "ls -l"

    def test_create_create_file_action(self):
        """
        Tests that the factory can create a valid CreateFileAction.
        """
        # Arrange
        raw_action = {
            "action": "create_file",
            "params": {"file_path": "/tmp/a", "content": "hello"},
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, CreateFileAction)
        assert action.file_path == "/tmp/a"
        assert action.content == "hello"

    def test_create_action_with_unknown_type_raises_error(self):
        """
        Tests that an unknown action type raises a ValueError.
        """
        # Arrange
        raw_action = {"action": "unknown_action"}

        # Act & Assert
        with pytest.raises(ValueError, match="Unknown action type: 'unknown_action'"):
            ActionFactory.create_action(raw_action)

    def test_create_action_with_missing_params_raises_error(self):
        """
        Tests that missing required params raises a TypeError.
        """
        # Arrange
        raw_action = {"action": "execute", "params": {}}

        # Act & Assert
        with pytest.raises(TypeError):
            ActionFactory.create_action(raw_action)
