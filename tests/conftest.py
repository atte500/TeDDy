import sys
from pathlib import Path
from unittest.mock import Mock
import pytest

from teddy_executor.core.ports.outbound import (
    IUserInteractor,
    IFileSystemManager,
    ISystemEnvironment,
    IShellExecutor,
    IWebScraper,
    IWebSearcher,
    IRepoTreeGenerator,
)

# Add the project root directory to the Python path.
# This is necessary to ensure that `pytest` can correctly resolve imports
# when running tests from a specific file path, as it might not add the
# project root to `sys.path` by default in that scenario.
# We add it to the beginning of the list to ensure it's checked first.
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def container(monkeypatch):
    """
    Provides a fresh DI container for each test and automatically
    patches the global container in teddy_executor.__main__.
    """
    from teddy_executor.container import create_container
    import teddy_executor.__main__

    c = create_container()
    monkeypatch.setattr(teddy_executor.__main__, "container", c)
    return c


@pytest.fixture
def mock_user_interactor(container):
    mock = Mock(spec=IUserInteractor)
    container.register(IUserInteractor, instance=mock)
    return mock


@pytest.fixture
def mock_fs(container):
    mock = Mock(spec=IFileSystemManager)
    container.register(IFileSystemManager, instance=mock)
    return mock


@pytest.fixture
def mock_env(container):
    mock = Mock(spec=ISystemEnvironment)
    container.register(ISystemEnvironment, instance=mock)
    return mock


@pytest.fixture
def mock_shell(container):
    mock = Mock(spec=IShellExecutor)
    container.register(IShellExecutor, instance=mock)
    return mock


@pytest.fixture
def mock_scraper(container):
    mock = Mock(spec=IWebScraper)
    container.register(IWebScraper, instance=mock)
    return mock


@pytest.fixture
def mock_searcher(container):
    mock = Mock(spec=IWebSearcher)
    container.register(IWebSearcher, instance=mock)
    return mock


@pytest.fixture
def mock_tree_gen(container):
    mock = Mock(spec=IRepoTreeGenerator)
    container.register(IRepoTreeGenerator, instance=mock)
    return mock
