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


def test_edit_fails_if_file_modified_externally(fs, container):
    """
    Mid-execution EDIT consistency: if a file is externally modified between
    two EDIT actions on the same file, the second EDIT must return FAILURE.
    """
    from teddy_executor.core.domain.models.plan import ActionData
    from teddy_executor.core.services.action_executor import ActionExecutor
    from teddy_executor.core.services.edit_simulator import EditSimulator
    from teddy_executor.adapters.outbound.local_file_system_adapter import (
        LocalFileSystemAdapter,
    )
    from teddy_executor.core.domain.models.execution_report import (
        ActionLog,
        ActionStatus,
    )
    from tests.harness.setup.mocking import register_mock
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher
    from teddy_executor.core.ports.outbound.config_service import IConfigService
    from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor

    # Arrange: create a target file
    fs.create_file("target.py", contents="original content")

    # Set up dependencies with auto-specced mocks via register_mock
    edit_sim = EditSimulator()
    file_system = LocalFileSystemAdapter(edit_simulator=edit_sim)
    action_dispatcher = register_mock(container, ActionDispatcher)
    user_interactor = register_mock(container, IUserInteractor)
    config_service = register_mock(container, IConfigService)

    executor = ActionExecutor(
        action_dispatcher=action_dispatcher,
        user_interactor=user_interactor,
        file_system_manager=file_system,
        edit_simulator=edit_sim,
        config_service=config_service,
    )

    # Success return for both dispatches
    action_dispatcher.dispatch_and_execute.return_value = ActionLog(
        status=ActionStatus.SUCCESS,
        action_type="EDIT",
        params={},
        modified=False,
        modified_fields=[],
    )

    # Create first EDIT action
    first_edit = ActionData(
        type="EDIT",
        params={"path": "target.py", "find": "original", "replace": "modified"},
        description="First edit",
    )

    # Act 1: dispatch first edit (interactive=False)
    log1, _ = executor.confirm_and_dispatch(
        first_edit, interactive=False, total_actions=2
    )
    assert log1.status == ActionStatus.SUCCESS

    # Arrange 2: externally modify the file
    file_system.write_file("target.py", "external change")

    # Create second EDIT action
    second_edit = ActionData(
        type="EDIT",
        params={"path": "target.py", "find": "modified", "replace": "final"},
        description="Second edit after external modification",
    )

    # Act 2: dispatch second edit
    log2, _ = executor.confirm_and_dispatch(
        second_edit, interactive=False, total_actions=2
    )

    # Assert: second edit must return FAILURE due to hash mismatch
    assert log2.status == ActionStatus.FAILURE, (
        "Second EDIT on externally modified file should fail with FAILURE status"
    )
