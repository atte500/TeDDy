import shutil
import uuid
from pathlib import Path
from typing import Any, Optional, TypeVar, cast
from unittest.mock import MagicMock, Mock, _Call
import teddy_executor.__main__
from teddy_executor.container import create_container
from tests.harness.setup.real_adapter_mixin import RealAdapterMixin

T = TypeVar("T")


class POSIXPathMock(MagicMock):
    """
    A specialized mock that normalizes the first string argument of any call
    AND any assertion to POSIX format. This ensures that unit tests are
    cross-platform and consistent with the core's Internal POSIX convention.
    """

    def _get_child_mock(self, /, **kw):
        return POSIXPathMock(**kw)

    def _normalize_args(self, args, kwargs):
        new_args = list(args)
        if new_args and isinstance(new_args[0], str):
            # Systemic normalization: replace \ with /
            new_args[0] = new_args[0].replace("\\", "/")
        return tuple(new_args), kwargs

    def __call__(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().__call__(*new_args, **new_kwargs)

    def assert_called_with(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_called_with(*new_args, **new_kwargs)

    def assert_any_call(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_any_call(*new_args, **new_kwargs)

    def assert_called_once_with(self, /, *args, **kwargs):
        new_args, new_kwargs = self._normalize_args(args, kwargs)
        return super().assert_called_once_with(*new_args, **new_kwargs)

    def assert_has_calls(self, calls, any_order=False):
        normalized_calls = []
        for call in calls:
            # call is a _Call object (tuple-like: (args, kwargs))
            args, kwargs = call[1], call[2]
            new_args, new_kwargs = self._normalize_args(args, kwargs)
            normalized_calls.append(_Call((new_args, new_kwargs), two=True))
        return super().assert_has_calls(normalized_calls, any_order=any_order)


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
        mock_fs = POSIXPathMock(spec=IFileSystemManager)
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

    # with_real_filesystem and with_real_init_service moved to RealAdapterMixin

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
