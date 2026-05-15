from __future__ import annotations

import punq


from teddy_executor.registries.infrastructure import register_infrastructure
from teddy_executor.registries.reviewer import register_reviewer
from teddy_executor.registries.validators import register_validators

_container = None


def get_container():
    global _container
    if _container is None:
        _container = create_container()
    return _container


def create_container() -> punq.Container:
    """
    Creates and configures the dependency injection container.
    """
    container = punq.Container()
    register_infrastructure(container)
    register_validators(container)
    _register_services(container)
    _register_orchestration(container)
    return container


def _register_services(container: punq.Container) -> None:
    """Registers core application services."""
    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.outbound import (
        IConfigService,
        IFileSystemManager,
        IMarkdownReportFormatter,
        IUserInteractor,
    )
    from teddy_executor.core.services.action_dispatcher import (
        ActionDispatcher,
        IActionFactory,
    )
    from teddy_executor.core.services.action_executor import ActionExecutor
    from teddy_executor.core.services.action_factory import ActionFactory
    from teddy_executor.core.services.edit_simulator import EditSimulator
    from teddy_executor.core.ports.outbound.session_repository import (
        ISessionRepository,
    )
    from teddy_executor.core.services.session_repository import SessionRepository
    from teddy_executor.core.services.markdown_plan_parser import MarkdownPlanParser
    from teddy_executor.core.services.markdown_report_formatter import (
        MarkdownReportFormatter,
    )
    from teddy_executor.core.services.session_loop_guard import (
        ProductionSessionLoopGuard,
    )
    from teddy_executor.core.domain.models.action_ports import ActionPorts

    container.register(
        ISessionRepository,
        factory=lambda: SessionRepository(container.resolve(IFileSystemManager)),
        scope=punq.Scope.transient,
    )
    container.register(IEditSimulator, EditSimulator, scope=punq.Scope.transient)
    container.register(IPlanParser, MarkdownPlanParser, scope=punq.Scope.transient)

    register_reviewer(container)

    from teddy_executor.core.ports.outbound import (
        IShellExecutor,
        IWebScraper,
        IWebSearcher,
    )
    from teddy_executor.core.ports.outbound.session_loop_guard import ISessionLoopGuard

    container.register(
        IActionFactory,
        factory=lambda: ActionFactory(
            ports=ActionPorts(
                shell_executor=container.resolve(IShellExecutor),
                file_system_manager=container.resolve(IFileSystemManager),
                user_interactor=container.resolve(IUserInteractor),
                web_scraper=container.resolve(IWebScraper),
                web_searcher=container.resolve(IWebSearcher),
                config_service=container.resolve(IConfigService),
            )
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
        ISessionLoopGuard, ProductionSessionLoopGuard, scope=punq.Scope.transient
    )
    _register_orchestration_services(container)


def _register_orchestration_services(container: punq.Container) -> None:
    """Registers orchestration and use case implementation services."""
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
        ISessionManager,
        IUserInteractor,
    )
    from teddy_executor.core.ports.outbound.execution_report_assembler import (
        IExecutionReportAssembler,
    )
    from teddy_executor.core.services.action_executor import ActionExecutor
    from teddy_executor.core.services.context_service import ContextService
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )
    from teddy_executor.core.services.execution_report_assembler import (
        ExecutionReportAssembler,
    )
    from teddy_executor.core.services.init_service import InitService
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.services.prompt_manager import PromptManager
    from teddy_executor.core.services.planning_service import PlanningService
    from teddy_executor.core.services.session_service import SessionService

    container.register(
        IExecutionReportAssembler, ExecutionReportAssembler, scope=punq.Scope.transient
    )
    container.register(
        ExecutionOrchestrator,
        factory=lambda: ExecutionOrchestrator(
            plan_parser=container.resolve(IPlanParser),
            plan_validator=container.resolve(IPlanValidator),
            action_executor=container.resolve(ActionExecutor),
            file_system_manager=container.resolve(IFileSystemManager),
            report_assembler=container.resolve(IExecutionReportAssembler),
            plan_reviewer=container.resolve(IPlanReviewer),
        ),
        scope=punq.Scope.transient,
    )
    container.register(ContextService, scope=punq.Scope.transient)
    container.register(IGetContextUseCase, ContextService, scope=punq.Scope.transient)
    from teddy_executor.core.domain.models.planning_ports import PlanningPorts

    container.register(
        IPromptManager,
        factory=lambda: PromptManager(
            file_system_manager=container.resolve(IFileSystemManager),
            user_interactor=container.resolve(IUserInteractor),
        ),
        scope=punq.Scope.transient,
    )

    container.register(
        PlanningPorts,
        factory=lambda: PlanningPorts(
            context=container.resolve(IGetContextUseCase),
            llm=container.resolve(ILlmClient),
            fs=container.resolve(IFileSystemManager),
            config=container.resolve(IConfigService),
            prompts=container.resolve(IPromptManager),
            ui=container.resolve(IUserInteractor),
            session_manager=container.resolve(ISessionManager),
        ),
        scope=punq.Scope.transient,
    )
    container.register(PlanningService, scope=punq.Scope.transient)
    container.register(IPlanningUseCase, PlanningService, scope=punq.Scope.transient)
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
    from teddy_executor.core.ports.outbound.time_service import ITimeService

    container.register(
        IInitUseCase,
        factory=lambda: InitService(container.resolve(IFileSystemManager)),
        scope=punq.Scope.transient,
    )

    container.register(
        ISessionManager,
        factory=lambda: SessionService(
            file_system_manager=container.resolve(IFileSystemManager),
            repository=container.resolve(ISessionRepository),
            time_service=container.resolve(ITimeService),
            prompt_manager=container.resolve(IPromptManager),
        ),
        scope=punq.Scope.transient,
    )


def _register_orchestration(container: punq.Container) -> None:
    """Registers session orchestration components."""
    from teddy_executor.core.ports.inbound.get_context_use_case import (
        IGetContextUseCase,
    )
    from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
    from teddy_executor.core.ports.inbound.planning_use_case import IPlanningUseCase
    from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
    from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
    from teddy_executor.core.ports.outbound import (
        IConfigService,
        IFileSystemManager,
        ILlmClient,
        IMarkdownReportFormatter,
        ISessionManager,
        IUserInteractor,
    )
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.services.execution_orchestrator import (
        ExecutionOrchestrator,
    )
    from teddy_executor.core.services.session_lifecycle_manager import (
        SessionLifecycleManager,
    )
    from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
    from teddy_executor.core.services.session_planner import SessionPlanner
    from teddy_executor.core.services.session_replanner import SessionReplanner
    from teddy_executor.core.services.session_pruning_service import (
        SessionPruningService,
    )

    container.register(
        SessionPruningService,
        factory=lambda: SessionPruningService(
            config_service=container.resolve(IConfigService),
            file_system_manager=container.resolve(IFileSystemManager),
        ),
        scope=punq.Scope.transient,
    )
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

    from teddy_executor.core.domain.models.planning_ports import SessionPorts

    container.register(
        SessionPorts,
        factory=lambda: SessionPorts(
            session_service=container.resolve(ISessionManager),
            file_system_manager=container.resolve(IFileSystemManager),
            report_formatter=container.resolve(IMarkdownReportFormatter),
            user_interactor=container.resolve(IUserInteractor),
            session_planner=container.resolve(SessionPlanner),
            replanner=container.resolve(SessionReplanner),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        SessionLifecycleManager,
        factory=lambda: SessionLifecycleManager(
            ports=container.resolve(SessionPorts),
        ),
        scope=punq.Scope.transient,
    )

    container.register(
        IRunPlanUseCase,
        factory=lambda: SessionOrchestrator(
            execution_orchestrator=container.resolve(ExecutionOrchestrator),
            session_service=container.resolve(ISessionManager),
            file_system_manager=container.resolve(IFileSystemManager),
            plan_validator=container.resolve(IPlanValidator),
            plan_parser=container.resolve(IPlanParser),
            user_interactor=container.resolve(IUserInteractor),
            lifecycle_manager=container.resolve(SessionLifecycleManager),
            replanner=container.resolve(SessionReplanner),
            context_service=container.resolve(IGetContextUseCase),
            config_service=container.resolve(IConfigService),
            llm_client=container.resolve(ILlmClient),
            prompt_manager=container.resolve(IPromptManager),
            pruning_service=container.resolve(SessionPruningService),
        ),
        scope=punq.Scope.transient,
    )
