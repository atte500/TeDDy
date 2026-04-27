import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, TypeVar, cast
from unittest.mock import Mock
import teddy_executor.__main__
from teddy_executor.container import create_container
from tests.harness.setup.real_adapter_mixin import RealAdapterMixin
from tests.harness.setup.mocking import POSIXPathMock, register_mock

T = TypeVar("T")


class TestEnvironment(RealAdapterMixin):
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

    # Real adapter registration methods moved to RealAdapterMixin

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

        self._deep_swap_container()

        # Legacy Compatibility: If a workspace was EXPLICITLY provided, anchor real adapters.
        # For managed workspaces (automated), we stay with mocks by default.
        if not self._is_managed_workspace and self.workspace:
            self._anchor_workspace()

        return self

    def _deep_swap_container(self) -> None:
        """
        Forcefully replaces the global container singleton.
        This bypasses punq's internal shadowing (where an 'instance' registration
        prevents subsequent re-registration of the same key).
        """
        import teddy_executor.container

        # 1. Update the local container reference
        # 2. Monkeypatch the global container used by the CLI
        self._monkeypatch.setattr(
            teddy_executor.container, "_container", self.container
        )

        # 3. Ensure the getter returns the correctly patched container
        # Note: This is redundant but ensures maximum visibility
        self._monkeypatch.setattr(
            teddy_executor.container, "get_container", lambda: self.container
        )

    def _register_default_mocks(self) -> None:
        """Registers mocks for side-effect-prone outbound ports (PLR0915)."""
        self._register_system_mocks()
        self._register_ui_mocks()
        self._register_ai_mocks()
        self._register_io_mocks()

    def _register_system_mocks(self) -> None:
        from teddy_executor.core.ports.outbound import (
            IShellExecutor,
            ISystemEnvironment,
        )

        mock_env = self.mock_port(ISystemEnvironment)
        mock_env.get_env.return_value = None
        mock_env.which.return_value = None

        mock_shell = self.mock_port(IShellExecutor)
        mock_shell.execute.return_value = {"stdout": "", "stderr": "", "return_code": 0}

    def _register_ui_mocks(self) -> None:
        import typer
        from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
        from teddy_executor.core.ports.outbound import IUserInteractor

        mock_interactor = self.mock_port(IUserInteractor)
        mock_interactor.confirm_action.return_value = (True, "")
        mock_interactor.confirm_manual_handoff.return_value = (True, "")
        mock_interactor.ask_question.return_value = ""
        # Ensure messages are visible in CLI output for assertions
        mock_interactor.display_message.side_effect = lambda m: typer.echo(m)
        self._container.register(IPlanReviewer, instance=None)

    def _register_ai_mocks(self) -> None:
        from teddy_executor.core.ports.outbound import (
            ILlmClient,
            IWebScraper,
            IWebSearcher,
        )

        mock_llm = self.mock_port(ILlmClient)
        mock_response = POSIXPathMock()
        mock_response.choices = [POSIXPathMock()]
        mock_response.choices[
            0
        ].message.content = "# Plan\n## Action Plan\n### EXECUTE\necho 1"
        mock_response.model = "test-model"
        mock_llm.get_completion.return_value = mock_response
        mock_llm.get_completion_cost.return_value = 0.0
        mock_llm.get_token_count.return_value = 0

        self.mock_port(IWebScraper)
        self.mock_port(IWebSearcher)

    def _register_io_mocks(self) -> None:
        from teddy_executor.core.ports.outbound import (
            IConfigService,
            IEnvironmentInspector,
            IFileSystemManager,
            IRepoTreeGenerator,
        )

        mock_fs = self.mock_port(IFileSystemManager)
        mock_fs.path_exists.return_value = False
        mock_fs.get_context_paths.return_value = {}
        mock_fs.read_files_in_vault.return_value = {}

        mock_config = self.mock_port(IConfigService)
        mock_config.get_setting.side_effect = lambda k, d=None: (
            None if k == "ui_mode" else d
        )

        mock_tree = self.mock_port(IRepoTreeGenerator)
        mock_tree.generate_tree.return_value = ""

        mock_inspector = self.mock_port(IEnvironmentInspector)
        mock_inspector.get_git_status.return_value = None

    # with_real_filesystem and with_real_init_service moved to RealAdapterMixin

    def _anchor_workspace(self) -> None:
        """Deprecated: Use with_real_filesystem() and with_real_init_service() instead."""
        self.with_real_filesystem()
        self.with_real_init_service()

    def mock_port(self, port_type: Any) -> Any:
        """
        Creates, registers, and returns a POSIXPathMock for a specific port.
        This is the preferred way to mock dependencies in tests.
        """
        return register_mock(self._container, port_type)

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
