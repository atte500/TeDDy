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
        "auto_pruning.prune_preceding_on_non_green": True,
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
