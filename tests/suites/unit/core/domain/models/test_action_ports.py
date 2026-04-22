from unittest.mock import MagicMock
from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound import (
    IShellExecutor,
    IFileSystemManager,
    IUserInteractor,
    IWebScraper,
    IWebSearcher,
    IConfigService,
)


def test_action_ports_initialization():
    # Arrange
    shell = MagicMock(spec=IShellExecutor)
    fs = MagicMock(spec=IFileSystemManager)
    user = MagicMock(spec=IUserInteractor)
    scraper = MagicMock(spec=IWebScraper)
    searcher = MagicMock(spec=IWebSearcher)
    config = MagicMock(spec=IConfigService)

    # Act
    ports = ActionPorts(
        shell_executor=shell,
        file_system_manager=fs,
        user_interactor=user,
        web_scraper=scraper,
        web_searcher=searcher,
        config_service=config,
    )

    # Assert
    assert ports.shell_executor == shell
    assert ports.file_system_manager == fs
    assert ports.user_interactor == user
    assert ports.web_scraper == scraper
    assert ports.web_searcher == searcher
    assert ports.config_service == config


def test_action_ports_config_is_optional():
    # Arrange
    shell = MagicMock(spec=IShellExecutor)
    fs = MagicMock(spec=IFileSystemManager)
    user = MagicMock(spec=IUserInteractor)
    scraper = MagicMock(spec=IWebScraper)
    searcher = MagicMock(spec=IWebSearcher)

    # Act
    ports = ActionPorts(
        shell_executor=shell,
        file_system_manager=fs,
        user_interactor=user,
        web_scraper=scraper,
        web_searcher=searcher,
    )

    # Assert
    assert ports.config_service is None
