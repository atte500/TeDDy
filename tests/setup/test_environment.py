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
        self.container = None

    def setup(self):
        """Initializes a fresh container and patches the global CLI container."""
        self.container = create_container()

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
            self.container.register(
                IFileSystemManager, LocalFileSystemAdapter, root_dir=str(self.workspace)
            )

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
