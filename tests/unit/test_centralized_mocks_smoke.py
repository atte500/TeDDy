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
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.run_plan_use_case import RunPlanUseCase
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.action_dispatcher import (
    ActionDispatcher,
    IActionFactory,
)
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


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


def test_mock_action_factory_is_registered(container, mock_action_factory):
    """Verifies that mock_action_factory fixture registers itself in the container."""
    resolved = container.resolve(IActionFactory)
    assert resolved is mock_action_factory
    assert isinstance(resolved, Mock)


def test_mock_plan_parser_is_registered(container, mock_plan_parser):
    """Verifies that mock_plan_parser fixture registers itself in the container."""
    resolved = container.resolve(IPlanParser)
    assert resolved is mock_plan_parser
    assert isinstance(resolved, Mock)


def test_mock_action_dispatcher_is_registered(container, mock_action_dispatcher):
    """Verifies that mock_action_dispatcher fixture registers itself in the container."""
    resolved = container.resolve(ActionDispatcher)
    assert resolved is mock_action_dispatcher
    assert isinstance(resolved, Mock)


def test_mock_run_plan_is_registered(container, mock_run_plan):
    """Verifies that mock_run_plan fixture registers itself in the container."""
    resolved_by_port = container.resolve(RunPlanUseCase)
    assert resolved_by_port is mock_run_plan
    assert isinstance(resolved_by_port, Mock)

    resolved_by_class = container.resolve(ExecutionOrchestrator)
    assert resolved_by_class is mock_run_plan


def test_mock_context_service_is_registered(container, mock_context_service):
    """Verifies that mock_context_service fixture registers itself in the container."""
    resolved_by_port = container.resolve(IGetContextUseCase)
    assert resolved_by_port is mock_context_service
    assert isinstance(resolved_by_port, Mock)

    resolved_by_class = container.resolve(ContextService)
    assert resolved_by_class is mock_context_service
