"""Shared fixtures for the core service unit tests."""

import pytest

from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.services.action_factory import ActionFactory


@pytest.fixture
def factory(  # noqa: PLR0913  # Six port mocks mirror the constructor.
    mock_shell,
    mock_fs,
    mock_user_interactor,
    mock_scraper,
    mock_searcher,
    mock_config,
) -> ActionFactory:
    """Provides an ActionFactory wired to the shared port mocks.

    The factory reads configuration when an action executes, so a test can
    override ``mock_config.get_setting`` after this fixture resolves.
    """
    ports = ActionPorts(
        shell_executor=mock_shell,
        file_system_manager=mock_fs,
        user_interactor=mock_user_interactor,
        web_scraper=mock_scraper,
        web_searcher=mock_searcher,
        config_service=mock_config,
    )
    return ActionFactory(ports)
