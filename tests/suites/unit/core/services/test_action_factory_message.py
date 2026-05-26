from unittest.mock import create_autospec
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.outbound.shell_executor import IShellExecutor
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.web_scraper import WebScraper
from teddy_executor.core.ports.outbound.web_searcher import IWebSearcher
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_action_factory_resolves_message_action():
    # Arrange
    # Use POSIXPathMock with spec to prevent signature drift (Anti-Mock Poisoning)
    # while satisfying the Ruff ban on bare MagicMock.
    mock_interactor = create_autospec(IUserInteractor, instance=True)
    ports = ActionPorts(
        shell_executor=POSIXPathMock(spec=IShellExecutor),
        file_system_manager=POSIXPathMock(spec=IFileSystemManager),
        user_interactor=mock_interactor,
        web_scraper=POSIXPathMock(spec=WebScraper),
        web_searcher=POSIXPathMock(spec=IWebSearcher),
        config_service=POSIXPathMock(spec=IConfigService),
    )
    factory = ActionFactory(ports)
    message_content = "Hello, this is a structural message."

    # Act
    params = {"content": message_content}
    action = factory.create_action("MESSAGE", params)
    action.execute(**params)

    # Assert
    # The MESSAGE content should be passed as the 'prompt' argument to ask_question
    mock_interactor.ask_question.assert_called_once_with(
        message_content, resources=None, agent_name=None
    )
