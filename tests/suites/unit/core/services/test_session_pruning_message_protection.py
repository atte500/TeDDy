import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.domain.models.project_context import ContextItem
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    service = create_autospec(IConfigService, instance=True)
    settings = {
        "auto_pruning.enabled": True,
        "auto_pruning.max_turns_retention": 1,
        "auto_pruning.preserve_message_turns": True,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
    }
    service.get_setting.side_effect = lambda key, default=None: settings.get(
        key, default
    )
    return service


@pytest.fixture
def mock_fs():
    mock = create_autospec(IFileSystemManager, instance=True)
    mock.path_exists.return_value = True
    return mock


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(
        config_service=mock_config,
        file_system_manager=mock_fs,
    )


def test_retention_limit_spares_successful_message_turns(service, mock_fs):
    """
    Logic: Successful Message turns should be spared from retention limit pruning.
    """
    # Arrange: Max retention is 1. Current turn is 02. Turn 01 should be pruned UNLESS it's a message.
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/plan.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    def mock_read(path):
        if "01/plan.md" in path:
            return "# Plan\n## Message\nHello User"
        if "01/report.md" in path:
            return "- **Overall Status:** Success"
        return ""

    mock_fs.read_file.side_effect = mock_read

    # Act
    result = service.prune(context)

    # Assert
    turn_01_plan = next(i for i in result.items if i.path == "01/plan.md")
    assert turn_01_plan.selected is True, (
        "Successful message turn should NOT be pruned by retention limit"
    )


def test_failure_pruning_spares_successful_message_turns(service, mock_fs):
    """
    Logic: Successful Message turns should NOT be pruned even if failure history pruning is active.
    """
    # Arrange: Turn 01 is a message turn. Turn 02 is a successful plan.
    # (Failure pruning usually prunes failures, but we want to ensure message turns are explicitly protected
    # if they were somehow flagged or if logic changes).
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="02/plan.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    def mock_read(path):
        if "01/plan.md" in path:
            # Contains Message but also some failure indicator elsewhere (e.g. status)
            return "- **Status:** 🟢\n## Message\nHello"
        return ""

    mock_fs.read_file.side_effect = mock_read

    # Act
    result = service.prune(context, current_status="SUCCESS 🟢")

    # Assert
    turn_01_plan = next(i for i in result.items if i.path == "01/plan.md")
    assert turn_01_plan.selected is True
