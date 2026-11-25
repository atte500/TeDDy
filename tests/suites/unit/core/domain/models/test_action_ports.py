"""Contract tests for the ``ActionPorts`` DTO.

Every double comes from ``register_mock``, so each is auto-specced to the port
it stands in for instead of being a bare dynamic mock.
"""

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IFileSystemManager,
    IShellExecutor,
    IUserInteractor,
    IWebSearcher,
)
from tests.harness.setup.mocking import register_mock


def test_action_ports_initialization(container):
    # Arrange
    shell = register_mock(container, IShellExecutor)
    fs = register_mock(container, IFileSystemManager)
    user = register_mock(container, IUserInteractor)
    searcher = register_mock(container, IWebSearcher)
    config = register_mock(container, IConfigService)

    # Act
    ports = ActionPorts(
        shell_executor=shell,
        file_system_manager=fs,
        user_interactor=user,
        web_searcher=searcher,
        config_service=config,
    )

    # Assert
    assert ports.shell_executor == shell
    assert ports.file_system_manager == fs
    assert ports.user_interactor == user
    assert ports.web_searcher == searcher
    assert ports.config_service == config


def test_action_ports_config_is_optional(container):
    # Arrange
    shell = register_mock(container, IShellExecutor)
    fs = register_mock(container, IFileSystemManager)
    user = register_mock(container, IUserInteractor)
    searcher = register_mock(container, IWebSearcher)

    # Act
    ports = ActionPorts(
        shell_executor=shell,
        file_system_manager=fs,
        user_interactor=user,
        web_searcher=searcher,
    )

    # Assert
    assert ports.config_service is None
