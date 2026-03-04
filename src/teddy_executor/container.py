import punq
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound import (
    IConfigService,
    IEnvironmentInspector,
    IFileSystemManager,
    ILlmClient,
    IMarkdownReportFormatter,
    IRepoTreeGenerator,
    IShellExecutor,
    ISystemEnvironment,
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
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator
from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
from teddy_executor.core.services.markdown_report_formatter import (
    MarkdownReportFormatter,
)
from teddy_executor.core.services.plan_validator import PlanValidator
from teddy_executor.core.services.validation_rules.create import CreateActionValidator
from teddy_executor.core.services.validation_rules.edit import EditActionValidator
from teddy_executor.core.services.validation_rules.execute import ExecuteActionValidator
from teddy_executor.core.services.validation_rules.read import ReadActionValidator
from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.adapters.outbound.litellm_adapter import LiteLLMAdapter
from teddy_executor.adapters.outbound.local_file_system_adapter import (
    LocalFileSystemAdapter,
)
from teddy_executor.adapters.outbound.local_repo_tree_generator import (
    LocalRepoTreeGenerator,
)
from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
from teddy_executor.adapters.outbound.system_environment_adapter import (
    SystemEnvironmentAdapter,
)
from teddy_executor.adapters.outbound.system_environment_inspector import (
    SystemEnvironmentInspector,
)
from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter


def create_container() -> punq.Container:
    """
    Creates and configures the dependency injection container.
    """
    container = punq.Container()
    # Register core OS abstractions first
    container.register(ISystemEnvironment, SystemEnvironmentAdapter)
    container.register(IEnvironmentInspector, SystemEnvironmentInspector)

    # Register ports and adapters
    container.register(IShellExecutor, ShellAdapter)
    container.register(IEditSimulator, EditSimulator)
    container.register(IFileSystemManager, LocalFileSystemAdapter)
    container.register(IWebScraper, WebScraperAdapter)
    container.register(IUserInteractor, ConsoleInteractorAdapter)
    container.register(IWebSearcher, WebSearcherAdapter)
    container.register(IConfigService, YamlConfigAdapter)
    container.register(ILlmClient, LiteLLMAdapter)
    container.register(IRepoTreeGenerator, LocalRepoTreeGenerator)
    container.register(IPlanParser, MarkdownPlanParser)
    container.register(IActionFactory, ActionFactory)
    container.register(ActionDispatcher)
    container.register(CreateActionValidator)
    container.register(EditActionValidator)
    container.register(ExecuteActionValidator)
    container.register(ReadActionValidator)
    container.register(
        IPlanValidator,
        PlanValidator,
        validators=[
            container.resolve(CreateActionValidator),
            container.resolve(EditActionValidator),
            container.resolve(ExecuteActionValidator),
            container.resolve(ReadActionValidator),
        ],
    )
    container.register(IMarkdownReportFormatter, MarkdownReportFormatter)
    container.register(ExecutionOrchestrator)
    container.register(IGetContextUseCase, ContextService)
    return container
