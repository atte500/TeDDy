from unittest.mock import Mock
from teddy_executor.core.ports.outbound import (
    IUserInteractor,
    IFileSystemManager,
    ISystemEnvironment,
    IShellExecutor,
    IWebScraper,
    IWebSearcher,
    IRepoTreeGenerator,
)


def test_mock_user_interactor_is_registered(container, mock_user_interactor):
    """Verifies that mock_user_interactor fixture registers itself in the container."""
    resolved = container.resolve(IUserInteractor)
    assert resolved is mock_user_interactor
    assert isinstance(resolved, Mock)


def test_mock_fs_is_registered(container, mock_fs):
    """Verifies that mock_fs fixture registers itself in the container."""
    resolved = container.resolve(IFileSystemManager)
    assert resolved is mock_fs
    assert isinstance(resolved, Mock)


def test_mock_env_is_registered(container, mock_env):
    """Verifies that mock_env fixture registers itself in the container."""
    resolved = container.resolve(ISystemEnvironment)
    assert resolved is mock_env
    assert isinstance(resolved, Mock)


def test_mock_shell_is_registered(container, mock_shell):
    """Verifies that mock_shell fixture registers itself in the container."""
    resolved = container.resolve(IShellExecutor)
    assert resolved is mock_shell
    assert isinstance(resolved, Mock)


def test_mock_scraper_is_registered(container, mock_scraper):
    """Verifies that mock_scraper fixture registers itself in the container."""
    resolved = container.resolve(IWebScraper)
    assert resolved is mock_scraper
    assert isinstance(resolved, Mock)


def test_mock_searcher_is_registered(container, mock_searcher):
    """Verifies that mock_searcher fixture registers itself in the container."""
    resolved = container.resolve(IWebSearcher)
    assert resolved is mock_searcher
    assert isinstance(resolved, Mock)


def test_mock_tree_gen_is_registered(container, mock_tree_gen):
    """Verifies that mock_tree_gen fixture registers itself in the container."""
    resolved = container.resolve(IRepoTreeGenerator)
    assert resolved is mock_tree_gen
    assert isinstance(resolved, Mock)
