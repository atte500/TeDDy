from unittest.mock import MagicMock
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.config_service import IConfigService


def test_find_editor_prioritizes_config_setting():
    # Setup
    mock_env = MagicMock(spec=ISystemEnvironment)
    mock_config = MagicMock(spec=IConfigService)

    # Configure mock_config to return a specific editor
    mock_config.get_setting.return_value = "zed --wait"
    # Ensure which returns true for the command
    mock_env.which.side_effect = lambda x: f"/usr/local/bin/{x}" if x == "zed" else None

    helper = ConsoleToolingHelper(system_env=mock_env, config_service=mock_config)
    editor_cmd = helper.find_editor()

    # Assert
    assert editor_cmd == ["/usr/local/bin/zed", "--wait"]
    mock_config.get_setting.assert_called_once_with("editor")


def test_find_editor_falls_back_to_env_if_config_missing():
    mock_env = MagicMock(spec=ISystemEnvironment)
    mock_config = MagicMock(spec=IConfigService)

    mock_config.get_setting.return_value = None
    mock_env.get_env.side_effect = lambda x: (
        "nvim" if x in ["VISUAL", "EDITOR"] else None
    )
    mock_env.which.side_effect = lambda x: f"/usr/bin/{x}" if x == "nvim" else None

    helper = ConsoleToolingHelper(system_env=mock_env, config_service=mock_config)
    editor_cmd = helper.find_editor()

    assert editor_cmd == ["/usr/bin/nvim"]


def test_find_editor_falls_back_to_discovery_if_all_missing():
    mock_env = MagicMock(spec=ISystemEnvironment)
    mock_config = MagicMock(spec=IConfigService)

    mock_config.get_setting.return_value = None
    mock_env.get_env.return_value = None
    # 'code' is available on path
    mock_env.which.side_effect = lambda x: f"/usr/bin/{x}" if x == "code" else None

    helper = ConsoleToolingHelper(system_env=mock_env, config_service=mock_config)
    editor_cmd = helper.find_editor()

    assert editor_cmd == ["/usr/bin/code"]
