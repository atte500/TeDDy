def test_action_factory_injects_global_timeout_into_shell_execution(  # noqa: PLR0913
    mock_shell, mock_fs, mock_user_interactor, mock_scraper, mock_searcher, mock_config
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

    from teddy_executor.core.services.action_factory import ActionFactory
    from teddy_executor.core.domain.models.action_ports import ActionPorts

    factory = ActionFactory(
        ActionPorts(
            shell_executor=mock_shell,
            file_system_manager=mock_fs,
            user_interactor=mock_user_interactor,
            web_scraper=mock_scraper,
            web_searcher=mock_searcher,
            config_service=mock_config,
        )
    )
    action = factory.create_action("EXECUTE", params={"command": "echo test"})

    # Act
    action.execute(command="echo test")

    # Assert
    original_execute.assert_called_with(command="echo test", timeout=42)
