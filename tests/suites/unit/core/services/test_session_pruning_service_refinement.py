import pytest
from unittest.mock import MagicMock
from teddy_executor.core.services.session_pruning_service import SessionPruningService
from teddy_executor.core.domain.models import ProjectContext, ContextItem
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def mock_config():
    service = MagicMock(spec=IConfigService)
    service.get_setting.side_effect = lambda key, default=None: {
        "auto_pruning.enabled": True,
        "auto_pruning.global_context_threshold": 10000,
        "auto_pruning.prune_preceding_on_non_green": True,
        "auto_pruning.prune_validation_failures": True,
    }.get(key, default)
    return service


@pytest.fixture
def mock_fs():
    mock = MagicMock(spec=IFileSystemManager)
    mock.path_exists.return_value = True
    return mock


@pytest.fixture
def service(mock_config, mock_fs):
    return SessionPruningService(
        config_service=mock_config,
        file_system_manager=mock_fs,
    )


def test_pruning_preserves_failure_until_recovery(service, mock_fs):
    """
    Refinement: If the latest turn is 🔴, do NOT prune it.
    It must be preserved for investigation.
    """
    # Arrange: Turn 01 is 🔴
    items = [
        ContextItem(
            path="session/01/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/01/report.md", token_count=100, git_status="", scope="Turn"
        ),
    ]
    context = ProjectContext(items=items, header="", content="")

    mock_fs.read_file.return_value = "- **Status:** [OUTCOME: FAILURE] [STATE: 🔴]"

    # Act
    result = service.prune(context)

    # Assert: 01 items should NOT be pruned
    for item in result.items:
        assert item.selected is True, (
            f"Item {item.path} should not be pruned during active failure"
        )


def test_pruning_cleans_up_failures_after_recovery(service, mock_fs):
    """
    Refinement: If the latest turn is 🟢, prune all preceding 🔴/🟡 turns.
    """
    # Arrange: Turn 01 is 🔴, Turn 02 is 🟢
    items = [
        ContextItem(
            path="session/01/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/01/report.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/02/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/02/report.md", token_count=100, git_status="", scope="Turn"
        ),
    ]
    context = ProjectContext(items=items, header="", content="")

    def mock_read(path):
        if "01/plan.md" in path:
            return "- **Status:** [OUTCOME: FAILURE] [STATE: 🔴]"
        if "02/plan.md" in path:
            return "- **Status:** [OUTCOME: SUCCESS] [STATE: 🟢]"
        return ""

    mock_fs.read_file.side_effect = mock_read

    # Act
    result = service.prune(context)

    # Assert: 01 items should be pruned
    t1_items = [i for i in result.items if "01/" in i.path]
    for item in t1_items:
        assert item.selected is False
        assert (
            item.auto_prune_reason == "Pruned failure history after successful recovery"
        )

    # Turn 02 should remain selected
    t2_items = [i for i in result.items if "02/" in i.path]
    for item in t2_items:
        assert item.selected is True


def test_pruning_uses_specific_validation_failure_string(service, mock_fs):
    """
    Refinement: Update Validation Matching to target '- **Overall Status:** Validation Failed'.
    """
    # Arrange
    items = [
        ContextItem(
            path="session/01/plan.md", token_count=100, git_status="", scope="Turn"
        ),
        ContextItem(
            path="session/01/report.md", token_count=100, git_status="", scope="Turn"
        ),
    ]
    context = ProjectContext(items=items, header="", content="")

    # Only match the exact spec string
    mock_fs.read_file.return_value = "- **Overall Status:** Validation Failed"

    # Act
    result = service.prune(context)

    # Assert
    for item in result.items:
        assert item.selected is False
        assert item.auto_prune_reason == "Plan failed validation"
