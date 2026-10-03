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


def test_find_editor_returns_none_when_no_config_and_no_env(
    helper, mock_env, mock_config
):
    """When no editor is configured via config or env vars, find_editor() returns None."""
    mock_config.get_setting.return_value = None
    mock_env.get_env.return_value = None
    mock_env.which.return_value = None

    result = helper.find_editor()

    assert result is None


def test_find_editor_config_code_returns_without_flags(helper, mock_env, mock_config):
    """When editor config is "code", find_editor() should return the path
    without -r --wait flags (VS Code special-casing removed)."""
    mock_config.get_setting.return_value = "code"
    mock_env.get_env.return_value = None
    mock_env.which.side_effect = lambda x: "/usr/bin/code" if x == "code" else None

    result = helper.find_editor()

    # Expected: just the resolved path, no extra flags
    assert result == ["/usr/bin/code"], f"Expected ['/usr/bin/code'], got {result}"


@pytest.mark.parametrize("sentinel", ["disabled", "DISABLED", "  Disabled  "])
def test_find_editor_returns_none_for_disabled_sentinel(
    helper, mock_env, mock_config, sentinel
):
    """The "disabled" sentinel (case/whitespace-insensitive) makes find_editor()
    return None immediately, bypassing the VISUAL/EDITOR env fallback."""
    # Arrange - config carries the sentinel; env vars would otherwise resolve.
    mock_config.get_setting.return_value = sentinel
    mock_env.get_env.side_effect = lambda x: (
        "nvim" if x in ("VISUAL", "EDITOR") else None
    )
    mock_env.which.side_effect = lambda x: "/usr/bin/nvim" if x == "nvim" else None

    # Act
    result = helper.find_editor()

    # Assert - disabled wins and the env fallback is never consulted.
    assert result is None
    mock_env.get_env.assert_not_called()


def test_diff_viewer_returns_none_when_fallback_not_taken(
    helper, mock_env, mock_config
):
    """When no config/env is set but which('code') returns a path,
    get_diff_viewer_command() should return None (fallback chain removed)."""
    mock_config.get_setting.return_value = None
    mock_env.get_env.return_value = None
    # which returns a path for 'code' to simulate old fallback trigger
    mock_env.which.side_effect = lambda x: "/usr/bin/code" if x == "code" else None

    result = helper.get_diff_viewer_command()

    assert result is None, f"Expected None, got {result}"


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

    def test_diff_viewer_returns_editor_path_for_unknown_editor(
        self, helper, mock_env, mock_config
    ):
        """For a resolved editor absent from the translation table (e.g. nano),
        get_diff_viewer_command returns the editor path with no flags, so the
        caller can open both files as separate arguments."""
        mock_config.get_setting.return_value = "nano"
        mock_env.get_env.side_effect = lambda x: None
        mock_env.which.side_effect = lambda x: "/usr/bin/nano" if x == "nano" else None

        result = helper.get_diff_viewer_command()

        assert result == ["/usr/bin/nano"]

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


def test_known_editors_lists_the_curated_editor_set():
    """The KNOWN_EDITORS Seam pins the curated PATH-discovery list (spec 2a).

    It must be a list of unique editor-name strings equal to the curated set
    scanned by the (later) discover_editors() method.
    """
    # Arrange - the curated contract from spec 2a
    expected = {
        # Terminal editors (modern)
        "nvim",
        "vim",
        "vi",
        "helix",
        "hx",
        "nano",
        "micro",
        "kak",
        "emacs",
        "ne",
        "joe",
        "ed",
        "ex",
        "mg",
        "zee",
        "amp",
        # GUI editors
        "code",
        "codium",
        "cursor",
        "zed",
        "sublime_text",
        "subl",
        "atom",
        "pulsar",
        "brackets",
        "idea",
        "idea.sh",
        "webstorm",
        "phpstorm",
        "pycharm",
        "rubymine",
        "goland",
        "clion",
        "fleet",
        "eclipse",
        "netbeans",
        "bluefish",
        "gedit",
        "gnome-text-editor",
        "kate",
        "kwrite",
        "mousepad",
        "xed",
        "pluma",
        "leafpad",
        "geany",
        "notepadqq",
        "notepad++",
        "notepad",
        "wordpad",
        "vimr",
        "macvim",
        "textmate",
        "bbedit",
        "ultraedit",
        "windsurf",
        "tabnine",
        "tea",
        "cot",
        "textastic",
        "nova",
        "xcode",
        "android-studio",
    }

    # Act
    known = ConsoleToolingHelper.KNOWN_EDITORS

    # Assert - a list of unique strings matching the curated set exactly
    assert isinstance(known, list)
    assert all(isinstance(name, str) for name in known)
    assert len(known) == len(set(known)), "KNOWN_EDITORS must not contain duplicates"
    assert set(known) == expected


def test_discover_editors_returns_known_editors_found_in_path(helper, mock_env):
    """discover_editors returns (name, path) pairs for editors found on PATH,
    ordered by KNOWN_EDITORS."""
    # Arrange - only a subset of KNOWN_EDITORS is available on PATH
    which_map = {
        "nvim": "/usr/local/bin/nvim",
        "vim": "/usr/bin/vim",
        "code": "/usr/bin/code",
    }
    mock_env.which.side_effect = lambda name: which_map.get(name)

    # Act
    result = helper.discover_editors()

    # Assert - ordered by KNOWN_EDITORS (nvim, vim, ... code)
    assert result == [
        ("nvim", "/usr/local/bin/nvim"),
        ("vim", "/usr/bin/vim"),
        ("code", "/usr/bin/code"),
    ]


def test_discover_editors_deduplicates_by_resolved_path(helper, mock_env):
    """discover_editors reports a binary reachable under two aliases only once,
    under its first KNOWN_EDITORS name."""
    # Arrange - 'vim' and 'vi' resolve to the SAME underlying binary
    mock_env.which.side_effect = lambda name: (
        "/usr/bin/shared-editor" if name in ("vim", "vi") else None
    )

    # Act
    result = helper.discover_editors()

    # Assert - deduplicated by resolved path, first alias wins
    assert result == [("vim", "/usr/bin/shared-editor")]


def test_discover_editors_returns_empty_list_when_none_found(helper, mock_env):
    """discover_editors returns an empty list when no known editor is on PATH."""
    # Arrange - nothing resolves
    mock_env.which.return_value = None

    # Act
    result = helper.discover_editors()

    # Assert
    assert result == []


@pytest.mark.parametrize(
    "editor",
    [
        "idea.sh",
        "webstorm",
        "phpstorm",
        "pycharm",
        "rubymine",
        "goland",
        "clion",
        "fleet",
    ],
)
def test_diff_flags_translation_table_includes_jetbrains_editors(editor):
    """The _DIFF_FLAGS translation table registers the JetBrains-family editors
    (spec 2d) with their bare 'diff' subcommand token."""
    assert ConsoleToolingHelper._DIFF_FLAGS.get(editor) == ["diff"]
