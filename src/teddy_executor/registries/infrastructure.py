from __future__ import annotations
import punq


def register_infrastructure(container: punq.Container) -> None:
    """Registers core OS and infrastructure adapters."""
    from teddy_executor.core.ports.outbound import (
        IConfigService,
        IEnvironmentInspector,
        IFileSystemManager,
        ILlmClient,
        IRepoTreeGenerator,
        IShellExecutor,
        ISystemEnvironment,
        ITimeService,
        IUserInteractor,
        IWebScraper,
        IWebSearcher,
    )
    from teddy_executor.adapters.outbound.console_interactor import (
        ConsoleInteractorAdapter,
    )
    from teddy_executor.adapters.outbound.litellm_adapter import (
        LiteLLMAdapter,
        IOpenRouterHydrator,
    )
    from teddy_executor.adapters.outbound.openrouter_hydrator import (
        OpenRouterMetadataHydrator,
    )
    from teddy_executor.adapters.outbound.local_file_system_adapter import (
        LocalFileSystemAdapter,
    )
    from teddy_executor.adapters.outbound.local_repo_tree_generator import (
        LocalRepoTreeGenerator,
    )
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
    from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter
    from teddy_executor.adapters.outbound.shell_command_builder import (
        ShellCommandBuilder,
    )
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )
    from teddy_executor.adapters.outbound.system_environment_inspector import (
        SystemEnvironmentInspector,
    )
    from teddy_executor.adapters.outbound.system_time_adapter import SystemTimeAdapter
    from teddy_executor.adapters.outbound.web_scraper_adapter import WebScraperAdapter
    from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
    from teddy_executor.adapters.outbound.yaml_config_adapter import YamlConfigAdapter

    container.register(
        ISystemEnvironment,
        factory=lambda: SystemEnvironmentAdapter(),
        scope=punq.Scope.transient,
    )
    container.register(
        IEnvironmentInspector,
        factory=lambda: SystemEnvironmentInspector(),
        scope=punq.Scope.transient,
    )
    container.register(
        ITimeService,
        factory=lambda: SystemTimeAdapter(),
        scope=punq.Scope.transient,
    )
    container.register(
        ShellCommandBuilder,
        factory=lambda: ShellCommandBuilder(),
        scope=punq.Scope.transient,
    )

    container.register(
        IShellExecutor,
        factory=lambda: ShellAdapter(
            command_builder=container.resolve(ShellCommandBuilder),
            max_execute_lines=container.resolve(IConfigService).get_setting(
                "execution.max_output_lines"
            ),
        ),
        scope=punq.Scope.transient,
    )

    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator

    container.register(
        IFileSystemManager,
        factory=lambda: LocalFileSystemAdapter(
            edit_simulator=container.resolve(IEditSimulator),
            max_read_lines=container.resolve(IConfigService).get_setting(
                "read.max_lines"
            ),
        ),
        scope=punq.Scope.transient,
    )

    container.register(
        IWebScraper,
        factory=lambda: WebScraperAdapter(container.resolve(IConfigService)),
        scope=punq.Scope.transient,
    )

    container.register(
        IUserInteractor,
        factory=lambda: ConsoleInteractorAdapter(
            system_env=container.resolve(ISystemEnvironment),
            config_service=container.resolve(IConfigService),
        ),
        scope=punq.Scope.transient,
    )

    container.register(
        IWebSearcher,
        factory=lambda: WebSearcherAdapter(
            config_service=container.resolve(IConfigService),
            scraper=container.resolve(IWebScraper),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        IConfigService, factory=lambda: YamlConfigAdapter(), scope=punq.Scope.transient
    )
    container.register(
        IOpenRouterHydrator,
        factory=lambda: OpenRouterMetadataHydrator(),
        scope=punq.Scope.singleton,
    )
    container.register(
        ILlmClient,
        factory=lambda: LiteLLMAdapter(
            config_service=container.resolve(IConfigService),
            hydrator=container.resolve(IOpenRouterHydrator),
        ),
        scope=punq.Scope.transient,
    )
    container.register(
        IRepoTreeGenerator,
        factory=lambda: LocalRepoTreeGenerator(),
        scope=punq.Scope.transient,
    )
    container.register(
        ConsoleToolingHelper,
        factory=lambda: ConsoleToolingHelper(
            system_env=container.resolve(ISystemEnvironment),
            config_service=container.resolve(IConfigService),
        ),
        scope=punq.Scope.transient,
    )
