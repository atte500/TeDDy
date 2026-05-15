import pytest
from unittest.mock import create_autospec
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models import ProjectContext
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    service = create_autospec(IConfigService, instance=True)
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 10000,
        "auto_pruning.prune_failure_history": True,
        "auto_pruning.prune_validation_failures": True,
        "auto_pruning.max_turns_retention": 25,
    }.get(key, default)
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


def test_prune_accepts_current_status(service):
    """
    Contract: Verify that the prune method accepts the current_status argument.
    """
    # Arrange
    context = ProjectContext(items=[], header="", content="")

    # Act & Assert (Should not raise TypeError)
    service.prune(context, current_status="SUCCESS 🟢")


def test_prune_triggers_recovery_cleanup_via_current_status(service, mock_fs):
    """
    Logic: If current_status is Green, it should trigger pruning of preceding failures.
    """
    # Arrange
    from teddy_executor.core.domain.models.project_context import ContextItem

    # Use standard turn directory names (digits only) to match extraction logic
    items = [
        ContextItem(path="01/plan.md", scope="Turn", token_count=100, git_status=" "),
        ContextItem(path="01/report.md", scope="Turn", token_count=100, git_status=" "),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Mock file content to indicate Turn 01 was a failure
    def mock_read(path):
        if "01/plan.md" in path:
            return "- **Status:** Execution Failed 🔴"
        return ""

    mock_fs.read_file.side_effect = mock_read

    # Act
    # We simulate that the 'current' turn (not yet on disk) is Green
    result = service.prune(context, current_status="SUCCESS 🟢")

    # Assert
    pruned_paths = [i.path for i in result.items if not i.selected]
    assert "01/plan.md" in pruned_paths
    assert "01/report.md" in pruned_paths
    assert (
        result.items[0].auto_prune_reason
        == "Pruned failure history after successful recovery"
    )
