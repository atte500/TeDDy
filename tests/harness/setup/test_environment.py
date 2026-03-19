import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, TypeVar, cast
from unittest.mock import MagicMock, Mock
import teddy_executor.__main__
from teddy_executor.container import create_container

T = TypeVar("T")


class TestEnvironment:
    """
    Setup component in the Test Harness Triad.
    Manages the lifecycle of the DI container and workspace isolation.
    """

    __test__ = False

    def __init__(self, monkeypatch, workspace: Optional[Path] = None):
        self._monkeypatch = monkeypatch
        self.workspace = workspace
        self._is_managed_workspace = workspace is None
        self.container: Optional[teddy_executor.container.punq.Container] = None

    @property
    def _container(self) -> teddy_executor.container.punq.Container:
        """Type-safe internal access to the container."""
        if self.container is None:
            raise RuntimeError(
                "TestEnvironment.setup() must be called before accessing the container."
            )
        return self.container

    def with_real_shell(self) -> "TestEnvironment":
        """Re-registers the real ShellAdapter instead of the mock."""
        from teddy_executor.core.ports.outbound import IShellExecutor
        from teddy_executor.adapters.outbound.shell_adapter import ShellAdapter

        self._container.register(IShellExecutor, ShellAdapter)
        return self

    def with_real_interactor(self) -> "TestEnvironment":
        """Re-registers the real ConsoleInteractor instead of the mock."""
        from teddy_executor.core.ports.outbound import IUserInteractor
        from teddy_executor.adapters.outbound.console_interactor import (
            ConsoleInteractorAdapter,
        )

        self._container.register(IUserInteractor, ConsoleInteractorAdapter)
        return self

    def with_real_inspector(self) -> "TestEnvironment":
        """Re-registers the real SystemEnvironmentInspector instead of the mock."""
        from teddy_executor.core.ports.outbound import IEnvironmentInspector
        from teddy_executor.adapters.outbound.system_environment_inspector import (
            SystemEnvironmentInspector,
        )

        self._container.register(IEnvironmentInspector, SystemEnvironmentInspector)
        return self

    def with_real_tree_generator(self, root_dir: str) -> "TestEnvironment":
        """Re-registers the real LocalRepoTreeGenerator instead of the mock."""
        from teddy_executor.core.ports.outbound import IRepoTreeGenerator
        from teddy_executor.adapters.outbound.local_repo_tree_generator import (
            LocalRepoTreeGenerator,
        )

        self._container.register(
            IRepoTreeGenerator, lambda: LocalRepoTreeGenerator(root_dir=root_dir)
        )
        return self

    def with_real_web_scraper(self) -> "TestEnvironment":
        """Re-registers the real WebScraperAdapter instead of the mock."""
        from teddy_executor.core.ports.outbound import IWebScraper
        from teddy_executor.adapters.outbound.web_scraper_adapter import (
            WebScraperAdapter,
        )

        self._container.register(IWebScraper, WebScraperAdapter)
        return self

    def with_real_config(self) -> "TestEnvironment":
        """Re-registers the real YamlConfigAdapter instead of the mock."""
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

    def with_real_searcher(self) -> "TestEnvironment":
        """Re-registers the real WebSearcherAdapter instead of the mock."""
        from teddy_executor.core.ports.outbound import IWebSearcher
        from teddy_executor.adapters.outbound.web_searcher_adapter import (
            WebSearcherAdapter,
        )

        self._container.register(IWebSearcher, WebSearcherAdapter)
        return self

    def setup(self) -> "TestEnvironment":
        """Initializes a fresh container and patches the global CLI container."""
        if self._is_managed_workspace:
            base_tmp = Path(__file__).parent.parent.parent / ".tmp"
            unique_name = f"test_{uuid.uuid4().hex}"
            self.workspace = base_tmp / unique_name
            self.workspace.mkdir(parents=True, exist_ok=True)

        if self.container is None:
            self.container = create_container()
        self._register_default_mocks()

        # Monkeypatch the global container instance used by the CLI
        self._monkeypatch.setattr(teddy_executor.__main__, "container", self.container)

        # Legacy Compatibility: If a workspace was EXPLICITLY provided, anchor real adapters.
        # For managed workspaces (automated), we stay with mocks by default.
        if not self._is_managed_workspace and self.workspace:
            self._anchor_workspace()

        return self

    def _register_default_mocks(self) -> None:
        """Registers mocks for side-effect-prone outbound ports."""
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

        # System Environment & Shell
        mock_env = Mock(spec=ISystemEnvironment)
        mock_env.get_env.return_value = None
        mock_env.which.return_value = None
        self._container.register(ISystemEnvironment, instance=mock_env)

        mock_shell = Mock(spec=IShellExecutor)
        mock_shell.execute.return_value = {"stdout": "", "stderr": "", "return_code": 0}
        self._container.register(IShellExecutor, instance=mock_shell)

        # UI & Interaction
        mock_interactor = Mock(spec=IUserInteractor)
        mock_interactor.confirm_action.return_value = (True, "")
        mock_interactor.confirm_manual_handoff.return_value = (True, "")
        mock_interactor.ask_question.return_value = ""
        self._container.register(IUserInteractor, instance=mock_interactor)

        # LLM
        mock_llm = Mock(spec=ILlmClient)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = "# Plan\n## Action Plan\n### EXECUTE\necho 1"
        mock_response.model = "test-model"
        mock_llm.get_completion.return_value = mock_response
        mock_llm.get_completion_cost.return_value = 0.0
        mock_llm.get_token_count.return_value = 0
        self._container.register(ILlmClient, instance=mock_llm)

        # Filesystem
        mock_fs = Mock(spec=IFileSystemManager)
        mock_fs.path_exists.return_value = False
        self._container.register(IFileSystemManager, instance=mock_fs)

        # Configuration & Inspection
        mock_config = Mock(spec=IConfigService)
        mock_config.get_setting.side_effect = lambda key, default=None: default
        self._container.register(IConfigService, instance=mock_config)

        self._container.register(IWebScraper, instance=Mock(spec=IWebScraper))
        self._container.register(IWebSearcher, instance=Mock(spec=IWebSearcher))
        self._container.register(
            IRepoTreeGenerator, instance=Mock(spec=IRepoTreeGenerator)
        )
        self._container.register(
            IEnvironmentInspector, instance=Mock(spec=IEnvironmentInspector)
        )

    def with_real_filesystem(self) -> "TestEnvironment":
        """Anchors real Filesystem and Tree Generator to the workspace."""
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

    def with_real_init_service(self) -> "TestEnvironment":
        """Anchors a real InitService with correctly resolved template paths."""
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

    def _anchor_workspace(self) -> None:
        """Deprecated: Use with_real_filesystem() and with_real_init_service() instead."""
        self.with_real_filesystem()
        self.with_real_init_service()

    def get_service(self, service_type: Any) -> Any:
        """Resolves a service from the test-configured container."""
        if not self.container:
            raise RuntimeError(
                "TestEnvironment.setup() must be called before get_service()"
            )
        return self.container.resolve(service_type)

    def get_mock_filesystem(self) -> Mock:
        from teddy_executor.core.ports.outbound import IFileSystemManager

        return cast(Mock, self.get_service(IFileSystemManager))

    def get_mock_shell(self) -> Mock:
        from teddy_executor.core.ports.outbound import IShellExecutor

        return self.get_service(IShellExecutor)  # type: ignore

    def get_mock_user_interactor(self) -> Mock:
        from teddy_executor.core.ports.outbound import IUserInteractor

        return self.get_service(IUserInteractor)  # type: ignore

    def teardown(self):
        """Cleans up monkeypatches and resets state."""
        # Monkeypatching is automatically handled by the pytest fixture
        if self._is_managed_workspace and self.workspace and self.workspace.exists():
            shutil.rmtree(self.workspace, ignore_errors=True)
