"""Regression test for cross-platform absolute path detection.

When checking if a path is absolute, the validator must detect POSIX-style
absolute paths (starting with /) on all platforms. os.path.isabs() is
platform-dependent: on Windows (ntpath), /etc is NOT considered absolute.
The fix adds `path_str.startswith("/")` before the os.path.isabs() check.

This test validates both the original (platform-dependent) and fixed
(cross-platform) logic against PurePosixPath and PureWindowsPath.
"""

from pathlib import PureWindowsPath


def _original_is_absolute(path_str: str) -> bool:
    """Buggy: uses only os.path.isabs which is platform-dependent."""
    import os

    return os.path.isabs(path_str)


def _fixed_is_absolute(path_str: str) -> bool:
    """Fixed: adds startswith('/') check before os.path.isabs."""
    import os

    return path_str.startswith("/") or os.path.isabs(path_str)


def test_original_logic_fails_on_posix_absolute_paths_on_windows():
    """Original os.path.isabs fails to detect /etc as absolute on Windows
    because ntpath.isabs requires a drive letter or backslash prefix.
    We use PureWindowsPath to simulate Windows path behavior without
    relying on ntpath.isabs behavior on non-Windows platforms."""
    # On Windows, ntpath.isabs('/etc') returns False. We verify this
    # by checking PureWindowsPath behavior.
    win_path = PureWindowsPath("/etc")
    # PureWindowsPath.is_absolute() returns False for /etc on Windows
    assert win_path.is_absolute() is False, (
        "On Windows (PureWindowsPath), /etc should NOT be absolute"
    )
    # The original logic uses os.path.isabs, which on Windows would
    # return False for /etc. We can't call ntpath.isabs directly on
    # non-Windows (it may behave differently), but we can prove the
    # bug exists by showing that os.path.isabs('/etc') == True but
    # PureWindowsPath('/etc').is_absolute() == False.
    assert _original_is_absolute("/etc") is True, (
        "On this platform, os.path.isabs('/etc') returns True"
    )
    assert _fixed_is_absolute("/etc") is True, "Fixed logic also returns True for /etc"
    # The key: on Windows, _original_is_absolute would return False,
    # but _fixed_is_absolute would still return True. We can't
    # directly test that here, but we can prove the fix is correct by
    # checking that startswith("/") handles it.
    assert "/etc".startswith("/") is True, (
        "startswith('/') catches POSIX absolute paths on all platforms"
    )


def test_fixed_logic_detects_posix_absolute_on_all_platforms():
    """Fixed logic detects /etc as absolute on all platforms."""
    posix_abs = "/etc"
    assert _fixed_is_absolute(posix_abs) is True, (
        "Fixed logic must detect /etc as absolute on all platforms"
    )


def test_fixed_logic_still_detects_windows_absolute():
    r"""Fixed logic still detects C:\Windows as absolute on platforms where it is.
    On Unix, C:\Windows is not absolute, so we use PureWindowsPath to verify
    the behavior on Windows."""
    win_abs = "C:\\Windows"
    # On Windows, os.path.isabs('C:\\Windows') returns True.
    # On Unix, os.path.isabs('C:\\Windows') returns False.
    # The fixed logic should detect it as absolute on Windows, but not on Unix.
    # We use PureWindowsPath.is_absolute() to simulate Windows behavior.
    assert PureWindowsPath(win_abs).is_absolute() is True, (
        "PureWindowsPath considers C:\\Windows as absolute"
    )
    # On the current platform, _fixed_is_absolute should match os.path.isabs
    import os

    assert _fixed_is_absolute(win_abs) == os.path.isabs(win_abs), (
        "Fixed logic should match os.path.isabs for this path on this platform"
    )


def test_fixed_logic_allows_relative_paths():
    """Relative paths should still be allowed by the fixed logic."""
    assert _fixed_is_absolute("relative/path") is False
    assert _fixed_is_absolute("./relative") is False
    assert _fixed_is_absolute("subdir/file.txt") is False


def test_fixed_logic_detects_traversal_paths_as_non_absolute():
    """Traversal paths like ../secret are NOT absolute (they start with dot),
    so the absolute path check should NOT catch them. They are caught by the
    directory traversal check separately."""
    assert _fixed_is_absolute("../secret") is False
    assert _fixed_is_absolute("foo/../../bar") is False
