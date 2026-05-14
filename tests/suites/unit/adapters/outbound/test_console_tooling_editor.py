import pytest
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
from teddy_executor.core.ports.outbound.config_service import IConfigService


@pytest.fixture
def mock_env():
    return POSIXPathMock(spec=ISystemEnvironment)


@pytest.fixture
def mock_config():
    return POSIXPathMock(spec=IConfigService)


@pytest.fixture
def helper(mock_env, mock_config):
    return ConsoleToolingHelper(mock_env, mock_config)


def test_find_editor_prefers_config(helper, mock_env, mock_config):
    # Setup: Config specifies "zed --wait"
    mock_config.get_setting.return_value = "zed --wait"
    mock_env.get_env.return_value = None
    mock_env.which.side_effect = lambda x: f"/usr/bin/{x}" if x == "zed" else None

    result = helper.find_editor()

    assert result == ["/usr/bin/zed", "--wait"]
    mock_config.get_setting.assert_called_with("editor")


def test_find_editor_falls_back_to_env_if_config_missing(helper, mock_env, mock_config):
    # Setup: Config missing, Env has "cursor"
    mock_config.get_setting.return_value = None
    mock_env.get_env.side_effect = lambda x: "cursor" if x == "VISUAL" else None
    mock_env.which.side_effect = lambda x: f"/usr/bin/{x}" if x == "cursor" else None

    result = helper.find_editor()

    assert result == ["/usr/bin/cursor"]


def test_find_editor_falls_back_to_env_if_config_executable_invalid(
    helper, mock_env, mock_config
):
    # Setup: Config has "invalid", Env has "nano"
    mock_config.get_setting.return_value = "invalid"
    mock_env.get_env.side_effect = lambda x: "nano" if x == "EDITOR" else None
    mock_env.which.side_effect = lambda x: f"/usr/bin/{x}" if x == "nano" else None

    result = helper.find_editor()

    # It should skip "invalid" because which("invalid") returns None
    assert result == ["/usr/bin/nano"]


def test_find_editor_falls_back_to_code_then_nano(helper, mock_env, mock_config):
    # Setup: No config, No env, code missing, nano exists
    mock_config.get_setting.return_value = None
    mock_env.get_env.return_value = None
    mock_env.which.side_effect = lambda x: "/usr/bin/nano" if x == "nano" else None

    result = helper.find_editor()

    assert result == ["/usr/bin/nano"]
    # Verify order: code must be checked before nano
    calls = [call[0][0] for call in mock_env.which.call_args_list]
    assert "code" in calls
    assert calls.index("code") < calls.index("nano")


def test_find_editor_falls_back_to_code_with_flags(helper, mock_env, mock_config):
    # Setup: No config, No env, code exists
    mock_config.get_setting.return_value = None
    mock_env.get_env.return_value = None
    mock_env.which.side_effect = lambda x: "/usr/bin/code" if x == "code" else None

    result = helper.find_editor()

    assert result == ["/usr/bin/code", "-r", "--wait"]


def test_resolve_editor_cmd_appends_vscode_flags(helper, mock_env):
    """Verifies that resolving 'code' as a simple string appends reuse flags."""
    # Setup which() to resolve both short name and full path to the full path
    path = "/usr/local/bin/code"

    def which_mock(cmd):
        if cmd in ("code", path):
            return path
        return None

    mock_env.which.side_effect = which_mock

    # 1. Simple command string: should append flags
    assert helper._resolve_editor_cmd("code") == [path, "-r", "--wait"]

    # 2. Full path (but still ends with code): should append flags
    assert helper._resolve_editor_cmd(path) == [path, "-r", "--wait"]

    # 3. Command string with existing flags should have missing standard flags appended
    result = helper._resolve_editor_cmd("code --new-window")
    assert path in result
    assert "--new-window" in result
    assert "-r" in result
    assert "--wait" in result
