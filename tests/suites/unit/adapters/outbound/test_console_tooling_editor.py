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


class TestGetDiffViewerCommand:
    """Tests for the new translation-table-based get_diff_viewer_command.

    These tests verify that get_diff_viewer_command() uses the _DIFF_FLAGS
    translation table to return correct commands for known editors, returns
    None for unknown editors, and respects the TEDDY_DIFF_TOOL env var override.
    """

    def test_diff_viewer_returns_vim_diff_flags(self, helper, mock_env, mock_config):
        """For a vim-configured editor, get_diff_viewer_command should return
        the editor command with ['-d'] appended."""
        # Arrange: config has "vim", which resolves
        mock_config.get_setting.return_value = "vim"
        mock_env.get_env.side_effect = lambda x: (
            None
        )  # No env override for editor, no TEDDY_DIFF_TOOL
        mock_env.which.side_effect = lambda x: "/usr/bin/vim" if x == "vim" else None

        # Act
        result = helper.get_diff_viewer_command()

        # Assert
        assert result == ["/usr/bin/vim", "-d"]

    def test_diff_viewer_returns_nvim_diff_flags(self, helper, mock_env, mock_config):
        """For nvim, get_diff_viewer_command should return ['nvim', '-d']."""
        mock_config.get_setting.return_value = "nvim"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/nvim" if x == "nvim" else None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/nvim", "-d"]

    def test_diff_viewer_returns_code_diff_flags(self, helper, mock_env, mock_config):
        """For code, get_diff_viewer_command should return ['code', '--diff']
        (not the old '-r --wait' pattern)."""
        mock_config.get_setting.return_value = "code"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/code" if x == "code" else None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/code", "--diff"]

    def test_diff_viewer_returns_cursor_diff_flags(self, helper, mock_env, mock_config):
        """For cursor, get_diff_viewer_command should return ['cursor', '--diff']."""
        mock_config.get_setting.return_value = "cursor"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: (
            "/usr/bin/cursor" if x == "cursor" else None
        )

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/cursor", "--diff"]

    def test_diff_viewer_returns_zed_diff_flags(self, helper, mock_env, mock_config):
        """For zed, get_diff_viewer_command should return ['zed', '--diff']."""
        mock_config.get_setting.return_value = "zed"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/zed" if x == "zed" else None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/zed", "--diff"]

    def test_diff_viewer_returns_intellij_diff_flags(
        self, helper, mock_env, mock_config
    ):
        """For idea, get_diff_viewer_command should return ['idea', 'diff']."""
        mock_config.get_setting.return_value = "idea"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/idea" if x == "idea" else None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/idea", "diff"]

    def test_diff_viewer_returns_none_for_unknown_editor(
        self, helper, mock_env, mock_config
    ):
        """For nano (not in translation table), get_diff_viewer_command returns None."""
        mock_config.get_setting.return_value = "nano"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/nano" if x == "nano" else None

        result = helper.get_diff_viewer_command()

        assert result is None

    def test_diff_viewer_returns_none_when_no_editor_found(
        self, helper, mock_env, mock_config
    ):
        """When find_editor() returns None (no config, no env, no fallback),
        get_diff_viewer_command should return None."""
        mock_config.get_setting.return_value = None
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.return_value = None

        result = helper.get_diff_viewer_command()

        assert result is None

    def test_diff_viewer_respects_teddy_diff_tool_override(
        self, helper, mock_env, mock_config
    ):
        """When TEDDY_DIFF_TOOL env var is set, get_diff_viewer_command should
        return the custom tool command."""
        # Arrange: set TEDDY_DIFF_TOOL env var
        mock_env.get_env.side_effect = lambda x: (
            "meld" if x == "TEDDY_DIFF_TOOL" else None
        )
        mock_env.which.side_effect = lambda x: "/usr/bin/meld" if x == "meld" else None
        mock_config.get_setting.return_value = None  # No editor configured

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/meld"]

    def test_diff_viewer_respects_teddy_diff_tool_with_args(
        self, helper, mock_env, mock_config
    ):
        """TEDDY_DIFF_TOOL with arguments should be parsed correctly."""
        mock_env.get_env.side_effect = lambda x: (
            "meld --auto-compare" if x == "TEDDY_DIFF_TOOL" else None
        )
        mock_env.which.side_effect = lambda x: "/usr/bin/meld" if x == "meld" else None
        mock_config.get_setting.return_value = None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/meld", "--auto-compare"]

    def test_diff_viewer_returns_none_when_teddy_diff_tool_not_found(
        self, helper, mock_env, mock_config
    ):
        """If TEDDY_DIFF_TOOL points to a non-existent executable, return None."""
        mock_env.get_env.side_effect = lambda x: (
            "nonexistent-tool" if x == "TEDDY_DIFF_TOOL" else None
        )
        mock_env.which.return_value = None
        mock_config.get_setting.return_value = None

        result = helper.get_diff_viewer_command()

        assert result is None
