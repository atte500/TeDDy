"""Regression test for cross-platform .git path detection helper.

When monkeypatching `Path.exists` to control .git detection, the helper
function must use `self.name == ".git"` instead of `str(self).endswith("/.git")`
because on Windows, `Path.__str__` uses backslashes, making the forward-slash
check always fail.

This test directly validates both the original (buggy) and fixed (correct)
logic against PurePosixPath and PureWindowsPath to ensure the fix works
across platforms.
"""

from pathlib import PurePosixPath, PureWindowsPath


def _original_controlled_exists(self):
    """Buggy: uses Unix-only forward-slash endswith."""
    if str(self).endswith("/.git"):
        return False
    return True


def _fixed_controlled_exists(self):
    """Fixed: uses pathlib's platform-independent .name attribute."""
    if self.name == ".git":
        return False
    return True


def test_original_logic_fails_on_windows_paths():
    """The original endswith('/.git') check fails on Windows paths because
    str(WindowsPath) uses backslashes."""
    win_dotgit = PureWindowsPath("C:\\Users\\test\\.git")
    unix_dotgit = PurePosixPath("/home/user/project/.git")

    # Unix path works fine
    assert _original_controlled_exists(unix_dotgit) is False, (
        "Original logic should return False for Unix .git path"
    )

    # Windows path fails (returns True instead of False)
    assert _original_controlled_exists(win_dotgit) is True, (
        "Original logic should return True for Windows .git path (BUG)"
    )


def test_fixed_logic_works_on_both_platforms():
    """The fixed .name == '.git' check works on all platforms."""
    win_dotgit = PureWindowsPath("C:\\Users\\test\\.git")
    unix_dotgit = PurePosixPath("/home/user/project/.git")

    assert _fixed_controlled_exists(unix_dotgit) is False, (
        "Fixed logic should return False for Unix .git path"
    )
    assert _fixed_controlled_exists(win_dotgit) is False, (
        "Fixed logic should return False for Windows .git path"
    )


def test_non_git_paths_unaffected():
    """Paths that do not end in .git should always return True regardless of platform."""
    win_regular = PureWindowsPath("C:\\Users\\test\\some_folder")
    unix_regular = PurePosixPath("/home/user/project/some_folder")

    assert _original_controlled_exists(win_regular) is True
    assert _original_controlled_exists(unix_regular) is True
    assert _fixed_controlled_exists(win_regular) is True
    assert _fixed_controlled_exists(unix_regular) is True
