from __future__ import annotations

import punq


def create_container() -> punq.Container:
    """
    Creates and configures the dependency injection container.
    """
    container = punq.Container()
    _register_infrastructure(container)
    _register_validators(container)
    _register_services(container)
    _register_orchestration(container)
    return container


def _register_infrastructure(container: punq.Container) -> None:
    """Registers core OS and infrastructure adapters."""
    from teddy_executor.core.ports.outbound import (
        IConfigService,
        IEnvironmentInspector,
        IFileSystemManager,
        ILlmClient,
        IRepoTreeGenerator,
        IShellExecutor,
        ISystemEnvironment,
        IUserInteractor,
        IWebScraper,
        IWebSearcher,
    )
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )
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

    container.register(
        ISystemEnvironment, SystemEnvironmentAdapter, scope=punq.Scope.transient
    )
    container.register(
        IEnvironmentInspector, SystemEnvironmentInspector, scope=punq.Scope.transient
    )
    container.register(IShellExecutor, ShellAdapter, scope=punq.Scope.transient)
    container.register(
        IFileSystemManager, LocalFileSystemAdapter, scope=punq.Scope.transient
    )
    container.register(IWebScraper, WebScraperAdapter, scope=punq.Scope.transient)
    container.register(
        IUserInteractor, ConsoleInteractorAdapter, scope=punq.Scope.transient
    )
    container.register(IWebSearcher, WebSearcherAdapter, scope=punq.Scope.transient)
    container.register(IConfigService, YamlConfigAdapter, scope=punq.Scope.transient)
    container.register(
        ILlmClient,
        factory=lambda: LiteLLMAdapter(container.resolve(IConfigService)),
    )
    container.register(
        IRepoTreeGenerator, LocalRepoTreeGenerator, scope=punq.Scope.transient
    )


def _register_validators(container: punq.Container) -> None:
    """Registers action-specific and plan validators."""
    from teddy_executor.core.ports.outbound import IConfigService, IFileSystemManager
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.services.plan_validator import PlanValidator
    from teddy_executor.core.services.validation_rules.create import (
        CreateActionValidator,
    )
    from teddy_executor.core.services.validation_rules.edit import EditActionValidator
    from teddy_executor.core.services.validation_rules.execute import (
        ExecuteActionValidator,
    )
    from teddy_executor.core.services.validation_rules.read import ReadActionValidator
    from teddy_executor.core.services.validation_rules.prune import PruneActionValidator

    container.register(CreateActionValidator, scope=punq.Scope.transient)
    container.register(
        EditActionValidator,
        factory=lambda: EditActionValidator(
            container.resolve(IFileSystemManager), container.resolve(IConfigService)
        ),
        scope=punq.Scope.transient,
    )
    container.register(ExecuteActionValidator, scope=punq.Scope.transient)
    container.register(ReadActionValidator, scope=punq.Scope.transient)
    container.register(PruneActionValidator, scope=punq.Scope.transient)

    container.register(
        IPlanValidator,
        factory=lambda: PlanValidator(
            container.resolve(IFileSystemManager),
            validators=[
                container.resolve(CreateActionValidator),
                container.resolve(EditActionValidator),
                container.resolve(ExecuteActionValidator),
                container.resolve(ReadActionValidator),
                container.resolve(PruneActionValidator),
            ],
        ),
        scope=punq.Scope.transient,
    )


def _register_services(container: punq.Container) -> None:
    """Registers core application services."""
    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.inbound.init import IInitUseCase
    from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
    from teddy_executor.core.ports.outbound import (
        IConfigService,
        IFileSystemManager,
        ILlmClient,
        IMarkdownReportFormatter,
        ISessionManager,
        IUserInteractor,
    )
    from teddy_executor.core.services.action_dispatcher import (
        ActionDispatcher,
        IActionFactory,
    )
    from teddy_executor.core.services.action_executor import ActionExecutor
    from teddy_executor.core.services.action_factory import ActionFactory
    from teddy_executor.core.services.context_service import ContextService
    from teddy_executor.core.services.edit_simulator import EditSimulator
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )
    from teddy_executor.core.services.init_service import InitService
    from teddy_executor.core.services.planning_service import PlanningService
    from teddy_executor.core.services.session_service import SessionService
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
    from teddy_executor.core.services.markdown_report_formatter import (
        MarkdownReportFormatter,
    )

    container.register(IEditSimulator, EditSimulator, scope=punq.Scope.transient)
    container.register(IPlanParser, MarkdownPlanParser, scope=punq.Scope.transient)
    container.register(IPlanReviewer, instance=None)
    container.register(
        IActionFactory,
        factory=lambda: ActionFactory(
            container=container, config_service=container.resolve(IConfigService)
        ),
        scope=punq.Scope.transient,
    )
    container.register(ActionDispatcher, scope=punq.Scope.transient)
    container.register(
        ActionExecutor,
        factory=lambda: ActionExecutor(
            action_dispatcher=container.resolve(ActionDispatcher),
            user_interactor=container.resolve(IUserInteractor),
            file_system_manager=container.resolve(IFileSystemManager),
            edit_simulator=container.resolve(IEditSimulator),
            config_service=container.resolve(IConfigService),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        IMarkdownReportFormatter, MarkdownReportFormatter, scope=punq.Scope.transient
    )
    container.register(
        ExecutionOrchestrator,
        factory=lambda: ExecutionOrchestrator(
            plan_parser=container.resolve(IPlanParser),
            plan_validator=container.resolve(IPlanValidator),
            action_executor=container.resolve(ActionExecutor),
            file_system_manager=container.resolve(IFileSystemManager),
            plan_reviewer=container.resolve(IPlanReviewer),
        ),
        scope=punq.Scope.transient,
    )
    container.register(IGetContextUseCase, ContextService, scope=punq.Scope.transient)
    container.register(
        IPlanningUseCase,
        factory=lambda: PlanningService(
            context_service=container.resolve(IGetContextUseCase),
            llm_client=container.resolve(ILlmClient),
            file_system_manager=container.resolve(IFileSystemManager),
            config_service=container.resolve(IConfigService),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        IInitUseCase, InitService, config_dir=None, scope=punq.Scope.transient
    )
    container.register(ISessionManager, SessionService, scope=punq.Scope.transient)


def _register_orchestration(container: punq.Container) -> None:
    """Registers session orchestration components."""
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.ports.outbound import (
        IFileSystemManager,
        IMarkdownReportFormatter,
        ISessionManager,
        IUserInteractor,
    )
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )
    from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
    from teddy_executor.core.services.session_planner import SessionPlanner
    from teddy_executor.core.services.session_replanner import SessionReplanner

    container.register(
        SessionReplanner,
        factory=lambda: SessionReplanner(
            file_system_manager=container.resolve(IFileSystemManager),
            planning_service=container.resolve(IPlanningUseCase),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        SessionPlanner,
        factory=lambda: SessionPlanner(
            file_system_manager=container.resolve(IFileSystemManager),
            planning_service=container.resolve(IPlanningUseCase),
            user_interactor=container.resolve(IUserInteractor),
            session_service=container.resolve(ISessionManager),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        IRunPlanUseCase,
        factory=lambda: SessionOrchestrator(
            execution_orchestrator=container.resolve(ExecutionOrchestrator),
            session_service=container.resolve(ISessionManager),
            file_system_manager=container.resolve(IFileSystemManager),
            report_formatter=container.resolve(IMarkdownReportFormatter),
            plan_validator=container.resolve(IPlanValidator),
            planning_service=container.resolve(IPlanningUseCase),
            plan_parser=container.resolve(IPlanParser),
            user_interactor=container.resolve(IUserInteractor),
            replanner=container.resolve(SessionReplanner),
            session_planner=container.resolve(SessionPlanner),
        ),
        scope=punq.Scope.transient,
    )
