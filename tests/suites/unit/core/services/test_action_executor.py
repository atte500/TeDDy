import pytest
from tests.harness.setup.mocking import register_mock
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.services.edit_simulator import EditSimulator


@pytest.fixture
def executor(container):
    # Register and resolve via the container to ensure autospec'd mocks
    register_mock(container, ActionDispatcher)
    register_mock(container, IUserInteractor)
    register_mock(container, IFileSystemManager)
    register_mock(container, EditSimulator)
    register_mock(container, IConfigService)

    return container.resolve(ActionExecutor)


def test_executor_can_be_initialized(executor):
    """Smoke test to verify DI container and mocks."""
    assert executor is not None
    assert isinstance(executor, ActionExecutor)
