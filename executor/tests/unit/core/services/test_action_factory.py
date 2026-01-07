import pytest

from teddy.core.domain.models import ExecuteAction, CreateFileAction
from teddy.core.domain import models
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

    def test_create_read_action(self):
        """
        Tests that the factory can create a valid ReadAction.
        """
        # Arrange
        raw_action = {
            "action": "read",
            "params": {"source": "path/to/file.txt"},
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, models.ReadAction)
        assert action.source == "path/to/file.txt"

    def test_create_edit_action(self):
        """
        Tests that the factory can create a valid EditAction.
        """
        # Arrange
        raw_action = {
            "action": "edit",
            "params": {
                "file_path": "/tmp/a",
                "find": "old",
                "replace": "new",
            },
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, models.EditAction)
        assert action.file_path == "/tmp/a"
        assert action.find == "old"
        assert action.replace == "new"

    def test_create_chat_with_user_action(self):
        """
        Tests that the factory can create a valid ChatWithUserAction.
        """
        # Arrange
        raw_action = {
            "action": "chat_with_user",
            "params": {"prompt": "What is the meaning of life?"},
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, models.ChatWithUserAction)
        assert action.prompt == "What is the meaning of life?"

    def test_create_research_action(self):
        """
        Tests that the factory can create a valid ResearchAction.
        """
        # Arrange
        raw_action = {
            "action": "research",
            "params": {"queries": ["python typer", "pytest best practices"]},
        }

        # Act
        action = ActionFactory.create_action(raw_action)

        # Assert
        assert isinstance(action, models.ResearchAction)
        assert action.queries == ["python typer", "pytest best practices"]
