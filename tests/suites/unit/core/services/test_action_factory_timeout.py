from unittest.mock import Mock
from teddy_executor.core.ports.outbound import IShellExecutor, IConfigService
from teddy_executor.core.services.action_factory import ActionFactory


def test_action_factory_injects_global_timeout_into_shell_execution(container):
    """
    Asserts that ActionFactory retrieves the global default timeout
    and passes it to the shell executor.
    """
    # Arrange
    mock_config = Mock(spec=IConfigService)
    # Return 42 only for the timeout key
    mock_config.get_setting.side_effect = lambda key, default=None: (
        42 if key == "execution.default_timeout_seconds" else default
    )

    mock_shell = Mock(spec=IShellExecutor)
    # Save a reference to the mock method that will be replaced
    original_execute_mock = mock_shell.execute
    original_execute_mock.return_value = {"return_code": 0}

    # We need to re-register these in the container for this test
    container.register(IConfigService, instance=mock_config)
    container.register(IShellExecutor, instance=mock_shell)

    # This instantiation will trigger a TypeError until we update __init__
    factory = ActionFactory(container, config_service=mock_config)
    action = factory.create_action("EXECUTE", params={"command": "echo test"})

    # Act
    action.execute(command="echo test")

    # Assert
    # We check if the original mock method was called with the injected timeout
    original_execute_mock.assert_called_with(command="echo test", timeout=42)
