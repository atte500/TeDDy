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
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
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
        IUserInteractor,
        factory=lambda: ConsoleInteractorAdapter(
            system_env=container.resolve(ISystemEnvironment),
            config_service=container.resolve(IConfigService),
        ),
        scope=punq.Scope.transient,
    )
    container.register(IWebSearcher, WebSearcherAdapter, scope=punq.Scope.transient)
    container.register(
        IConfigService,
        factory=lambda: YamlConfigAdapter(),
        scope=punq.Scope.transient,
    )
    container.register(
        ILlmClient,
        factory=lambda: LiteLLMAdapter(container.resolve(IConfigService)),
    )
    container.register(
        IRepoTreeGenerator, LocalRepoTreeGenerator, scope=punq.Scope.transient
    )
    container.register(
        ConsoleToolingHelper,
        factory=lambda: ConsoleToolingHelper(
            system_env=container.resolve(ISystemEnvironment),
            config_service=container.resolve(IConfigService),
        ),
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
