import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.action_executor import ActionExecutor


@pytest.fixture
def mock_deps():
    return {
        "action_dispatcher": MagicMock(),
        "user_interactor": MagicMock(),
        "file_system_manager": MagicMock(),
        "edit_simulator": MagicMock(),
        "config_service": MagicMock(),
    }


@pytest.fixture
def executor(mock_deps):
    return ActionExecutor(**mock_deps)
