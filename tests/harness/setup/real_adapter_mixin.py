import os
from typing import Any


class RealAdapterMixin:
    """
    Mixin for TestEnvironment that handles the registration of real outbound adapters.
    """

    def with_real_shell(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IShellExecutor
        from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter

        self._container.register(IShellExecutor, ShellAdapter)
        return self

    def with_real_interactor(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IUserInteractor
        from teddy_executor.adapters.outbound.console_interactor import (
            ConsoleInteractorAdapter,
        )

        self._container.register(IUserInteractor, ConsoleInteractorAdapter)
        return self

    def with_real_inspector(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IEnvironmentInspector
        from teddy_executor.adapters.outbound.system_environment_inspector import (
            SystemEnvironmentInspector,
        )

        self._container.register(IEnvironmentInspector, SystemEnvironmentInspector)
        return self

    def with_real_tree_generator(self: Any, root_dir: str) -> Any:
        from teddy_executor.core.ports.outbound import IRepoTreeGenerator
        from teddy_executor.adapters.outbound.local_repo_tree_generator import (
            LocalRepoTreeGenerator,
        )

        self._container.register(
            IRepoTreeGenerator, lambda: LocalRepoTreeGenerator(root_dir=root_dir)
        )
        return self

    def with_real_web_scraper(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IWebScraper
        from teddy_executor.adapters.outbound.web_scraper_adapter import (
            WebScraperAdapter,
        )

        self._container.register(IWebScraper, WebScraperAdapter)
        return self

    def with_real_config(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IConfigService
        from teddy_executor.adapters.outbound.yaml_config_adapter import (
            YamlConfigAdapter,
        )

        config_path = (
            str(self.workspace / ".teddy" / "config.yaml")
            if self.workspace
            else ".teddy/config.yaml"
        )
        self._container.register(
            IConfigService, lambda: YamlConfigAdapter(config_path=config_path)
        )
        return self

    def with_real_searcher(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import IWebSearcher
        from teddy_executor.adapters.outbound.web_searcher_adapter import (
            WebSearcherAdapter,
        )

        self._container.register(IWebSearcher, WebSearcherAdapter)
        return self

    def with_real_filesystem(self: Any) -> Any:
        from teddy_executor.core.ports.outbound import (
            IFileSystemManager,
            IRepoTreeGenerator,
        )
        from teddy_executor.adapters.outbound.local_file_system_adapter import (
            LocalFileSystemAdapter,
        )
        from teddy_executor.adapters.outbound.local_repo_tree_generator import (
            LocalRepoTreeGenerator,
        )

        if not self.workspace:
            raise RuntimeError("Cannot anchor real filesystem without a workspace.")
        self._container.register(
            IFileSystemManager, LocalFileSystemAdapter, root_dir=str(self.workspace)
        )
        self._container.register(
            IRepoTreeGenerator, LocalRepoTreeGenerator, root_dir=str(self.workspace)
        )
        return self

    def with_real_init_service(self: Any) -> Any:
        from teddy_executor.core.ports.inbound.init import IInitUseCase
        from teddy_executor.core.services.init_service import InitService
        from teddy_executor.core.ports.outbound import IFileSystemManager

        real_config = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../config")
        )
        self._container.register(
            IInitUseCase,
            lambda: InitService(
                self.get_service(IFileSystemManager), config_dir=real_config
            ),
        )
        return self
