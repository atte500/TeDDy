from teddy_executor.core.services.action_factory import IActionFactory


def test_action_factory_injects_global_timeout_into_shell_execution(
    container, mock_config, mock_shell
):
    """
    Asserts that ActionFactory retrieves the global default timeout
    and passes it to the shell executor.
    """
    # Arrange
    # Return 42 only for the timeout key
    mock_config.get_setting.side_effect = lambda key, default=None: (
        42 if key == "execution.default_timeout_seconds" else default
    )

    mock_shell.execute.return_value = {"return_code": 0}
    # Capture the mock method before ActionFactory monkeypatches it
    original_execute = mock_shell.execute

    factory = container.resolve(IActionFactory)
    action = factory.create_action("EXECUTE", params={"command": "echo test"})

    # Act
    action.execute(command="echo test")

    # Assert
    original_execute.assert_called_with(command="echo test", timeout=42)
