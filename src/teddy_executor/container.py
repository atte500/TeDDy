import punq
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import (
    IEnvironmentInspector,
    IFileSystemManager,
    IMarkdownReportFormatter,
    IRepoTreeGenerator,
    IShellExecutor,
    IUserInteractor,
    IWebScraper,
    IWebSearcher,
)
from teddy_executor.core.services.action_dispatcher import (
    ActionDispatcher,
    IActionFactory,
)
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.context_service import ContextService
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter


def create_container() -> punq.Container:
    """
    Creates and configures the dependency injection container.
    Note: The RunPlanUseCase/ExecutionOrchestrator is not registered here
    because its PlanParser dependency is determined at runtime.
    """
    container = punq.Container()
    container.register(IShellExecutor, ShellAdapter)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IWebScraper, WebScraperAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)
    container.register(IWebSearcher, WebSearcherAdapter)
    container.register(IRepoTreeGenerator, LocalRepoTreeGenerator)
    container.register(IEnvironmentInspector, SystemEnvironmentInspector)
    container.register(IActionFactory, ActionFactory)
    container.register(ActionDispatcher)
    container.register(IPlanValidator, PlanValidator)
    container.register(IMarkdownReportFormatter, MarkdownReportFormatter)
    # PlanParser is now created by the factory
    # RunPlanUseCase is instantiated manually in the `execute` command
    container.register(IGetContextUseCase, ContextService)
    return container
