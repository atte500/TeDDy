from pathlib import Path
from typing import Optional, Type, TypeVar
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

    def setup(self) -> "TestEnvironment":
        """Initializes a fresh container and patches the global CLI container."""
        self.container = create_container()

        # Register mocks for side-effect-prone outbound ports by default
        from unittest.mock import MagicMock, Mock

        from teddy_executor.core.ports.outbound import (
            ILlmClient,
            IShellExecutor,
            ISystemEnvironment,
            IUserInteractor,
        )

        mock_env = Mock(spec=ISystemEnvironment)
        # Ensure env and which return None by default to prevent truthy Mock issues
        mock_env.get_env.return_value = None
        mock_env.which.return_value = None
        self._container.register(ISystemEnvironment, instance=mock_env)

        # Interactor MUST be unpack-safe for interactive sequences
        mock_interactor = Mock(spec=IUserInteractor)
        mock_interactor.confirm_action.return_value = (True, "")
        mock_interactor.confirm_manual_handoff.return_value = (True, "")
        mock_interactor.ask_question.return_value = ""
        self._container.register(IUserInteractor, instance=mock_interactor)

        mock_llm = Mock(spec=ILlmClient)
        # Create a structured ModelResponse mock for safe defaults
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = (
            "# Mock Plan\nRationale: Test\n## Action Plan\n### EXECUTE\necho 1"
        )
        mock_response.model = "test-model"
        mock_llm.get_completion.return_value = mock_response
        mock_llm.get_token_count.return_value = 100
        mock_llm.get_completion_cost.return_value = 0.01
        self._container.register(ILlmClient, instance=mock_llm)

        self._container.register(IShellExecutor, instance=Mock(spec=IShellExecutor))

        # Monkeypatch the global container instance used by the CLI
        self._monkeypatch.setattr(teddy_executor.__main__, "container", self.container)

        # Optionally anchor the workspace
        if self.workspace:
            from teddy_executor.core.ports.outbound.file_system_manager import (
                IFileSystemManager,
            )
            from teddy_executor.adapters.outbound.local_file_system_adapter import (
                LocalFileSystemAdapter,
            )

            # Re-register with the anchored root
            self._container.register(
                IFileSystemManager, LocalFileSystemAdapter, root_dir=str(self.workspace)
            )

        return self

    def get_service(self, service_type: Type[T]) -> T:
        """Resolves a service from the test-configured container."""
        if not self.container:
            raise RuntimeError(
                "TestEnvironment.setup() must be called before get_service()"
            )
        return self.container.resolve(service_type)

    def teardown(self):
        """Cleans up monkeypatches and resets state."""
        # Monkeypatching is automatically handled by the pytest fixture
        pass
