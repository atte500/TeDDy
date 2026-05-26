from teddy_executor.adapters.outbound.console_interactor import ConsoleInteractorAdapter
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def test_notify_warning_prints_formatted_message(
    mock_env: ISystemEnvironment, mock_config: IConfigService, capsys
):
    # Arrange
    adapter = ConsoleInteractorAdapter(mock_env, mock_config)
    warning_msg = "This is a test warning"

    # Act
    # This should fail with AttributeError
    adapter.notify_warning(warning_msg)

    # Assert
    captured = capsys.readouterr()
    # We expect the message to be in stderr since ConsoleInteractor uses stderr=True
    assert warning_msg in captured.err
    # Rich formatting often adds color codes, we just check for the text presence
    # and that it's generally styled as a warning.
    assert "WARNING" in captured.err.upper()
