"""Remote Probe: Verify git detection test fix on Windows.

This script reproduces the exact scenario from the three failing tests:
- test_check_git_not_detected_in_parent_repo_subfolder
- test_check_git_initialized_success
- test_check_git_initialized_failure

It tests both the original (broken) and fixed (proposed) controlled_exists logic
and reports pass/fail for each case.

Run: python spikes/debug/12-git-detection-rpp.py
"""
import sys
import os
from pathlib import Path

# Ensure we can import from src
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


# --- Simulated dependency: typer.secho ---
class FakeTyper:
    colors = type("Colors", (), {"GREEN": "green", "YELLOW": "yellow"})()
    messages = []

    @staticmethod
    def secho(msg, fg=None, err=None):
        FakeTyper.messages.append((msg, fg, err))
        print(f"  [secho] {msg!r} (fg={fg}, err={err})")


# --- The original (broken) controlled_exists ---
def original_controlled_exists(self):
    if str(self).endswith("/.git"):
        return False
    return True


# --- The fixed controlled_exists ---
def fixed_controlled_exists(self):
    if self.name == ".git":
        return False
    return True


def run_test(test_name, controlled_exists_fn, simulate_windows_style=True):
    """Run a test scenario simulating the failing test behavior.

    Args:
        test_name: Name for the test (for reporting).
        controlled_exists_fn: The function to monkeypatch Path.exists with.
        simulate_windows_style: If True, simulate the Windows path scenario
                                by monkeypatching Path.__str__ to return backslash paths.
    """
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")

    # Reset message collector
    FakeTyper.messages = []

    # Patch typer.secho globally
    import teddy_executor.adapters.inbound.session_cli_handlers as handlers
    original_secho = handlers.typer.secho
    handlers.typer.secho = FakeTyper.secho
    handlers.typer.colors = FakeTyper.colors

    # Patch shutil.which to simulate git CLI available
    import shutil
    original_which = shutil.which
    shutil.which = lambda cmd: "/usr/bin/git" if cmd == "git" else None

    # Patch Path.exists with the controlled function
    original_exists = Path.exists
    Path.exists = controlled_exists_fn

    # Determine the path that _check_git_initialized will check:
    # (Path.cwd() / ".git").exists()
    # We need to simulate that this check fails (returns False) when .git not in CWD.
    # On Windows, Path.cwd() / ".git" produces a WindowsPath with backslashes.
    # On Unix, it produces a PosixPath with forward slashes.
    # To simulate Windows on any platform, we can temporarily change the environment
    # to make Path.cwd() return a backslash-heavy path? Not clean.
    #
    # Instead, we rely on the fact that if simulate_windows_style is True,
    # the controlled_exists_fn will receive a path with backslashes because
    # we prepend a simulated situation. But that's hard.
    #
    # Better approach: directly test the helper function logic with example paths:
    # - On Windows: Path("C:\\Users\\test\\.git")
    # - On Unix: Path("/home/user/project/.git")
    # We'll call _check_git_initialized but its behavior depends on actual CWD.
    # Instead, we directly test the controlled_exists logic with realistic paths.

    print("\nDirect path simulation:")
    # Simulate the exact two paths that would be tested:
    # 1. A Unix path (as passed on Linux/macOS)
    unix_dotgit_path = Path("/home/user/project/.git")
    result_original = original_controlled_exists(unix_dotgit_path)
    result_fixed = fixed_controlled_exists(unix_dotgit_path)
    print(f"  Unix path: {unix_dotgit_path!r}")
    print(f"    original_controlled_exists(repr={str(unix_dotgit_path)!r}) endswith('/.git'): {str(unix_dotgit_path).endswith('/.git')}")
    print(f"    original result: exists={result_original}")
    print(f"    fixed_controlled_exists name='{unix_dotgit_path.name}': name=='.git' = {unix_dotgit_path.name == '.git'}")
    print(f"    fixed result: exists={result_fixed}")

    # 2. A Windows path (simulated as a string representation)
    # On actual Windows, Path("C:\\Users\\test\\.git") would be a WindowsPath.
    # On Unix, it's a PosixPath which treats backslashes as literal characters.
    # So the name will be the entire string. To properly test, we need the
    # string representation that would come from str(WindowsPath(...)).
    # We can simulate by creating a simple string.
    win_dotgit_str = "C:\\Users\\test\\.git"
    # What would str(WindowsPath("C:\\Users\\test\\.git")) look like?
    # It would be exactly that string.
    result_original_win = original_controlled_exists(type("FakePath", (), {"__str__": lambda s: win_dotgit_str})())
    # For the fixed version, we need a proper path-like object that supports .name.
    # Since we can't instantiate WindowsPath on Unix, we fake it.
    class FakeWindowsPath:
        def __str__(self):
            return win_dotgit_str
        @property
        def name(self):
            # On Windows, Path.name returns the last component after the last backslash
            return win_dotgit_str.split("\\")[-1]  # ".git"

    fake_win_path = FakeWindowsPath()
    result_fixed_win = fixed_controlled_exists(fake_win_path)
    print(f"\n  Windows path (simulated): {win_dotgit_str!r}")
    print(f"    original_controlled_exists: endswith('/.git') = {win_dotgit_str.endswith('/.git')}")
    print(f"    original result: exists={result_original_win}")
    print(f"    fixed_controlled_exists: name='{fake_win_path.name}'")
    print(f"    fixed result: exists={result_fixed_win}")

    # Now test the full _check_git_initialized scenario using our faked approach
    print("\nFull _check_git_initialized scenario (fixed logic):")
    # We'll monkeypatch Path.exists with the fixed version and ensure
    # that when _check_git_initialized calls (Path.cwd() / ".git").exists(),
    # our controlled_exists returns False for .git paths.
    # On Windows CI, the actual Path.cwd() will be a WindowsPath with backslashes.
    # So we rely on the fixed controlled_exists's self.name == ".git" behavior.
    # We'll patch CWD to be a subdirectory without .git.
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = Path.cwd()
        os.chdir(tmpdir)  # CWD is now tempdir (no .git)
        # The fixed controlled_exists should return False for (tmpdir/.git)
        # because tmpdir/.git ends with ".git" in name.
        dotgit = Path.cwd() / ".git"
        print(f"    CWD: {Path.cwd()}")
        print(f"    Checking: {dotgit!r}")
        print(f"    Fixed controlled_exists result: {fixed_controlled_exists(dotgit)}")
        print(f"    str(self).endswith('/.git') result: {str(dotgit).endswith('/.git')}")
        os.chdir(original_cwd)

    # Also test the actual function call with a mocked environment
    print("\nActual _check_git_initialized with fixed Path.exists:")
    # We need to monkeypatch Path.exists with the FIXED controlled_exists
    Path.exists = fixed_controlled_exists
    # Mock subprocess.run to succeed
    import subprocess
    original_subprocess_run = subprocess.run
    subprocess.run = lambda *args, **kwargs: type("FakeResult", (), {"returncode": 0})()
    # Call the function
    handlers._check_git_initialized()
    # Check messages
    print(f"  Messages after call: {FakeTyper.messages}")
    if len(FakeTyper.messages) == 1:
        msg, fg, err = FakeTyper.messages[0]
        if "Git repository initialized" in msg:
            print("  ✓ PASS: Got 'Git repository initialized' as expected")
        else:
            print(f"  ✗ FAIL: Unexpected message: {msg}")
    else:
        print(f"  ✗ FAIL: Expected 1 message, got {len(FakeTyper.messages)}")

    # Restore originals
    Path.exists = original_exists
    shutil.which = original_which
    handlers.typer.secho = original_secho
    subprocess.run = original_subprocess_run


if __name__ == "__main__":
    print("=== Remote Probe: Git Detection Windows Bug ===")
    print(f"Running on platform: {sys.platform}")

    run_test("Original logic (endswith '/.git')", original_controlled_exists)
    run_test("Fixed logic (name == '.git')", fixed_controlled_exists)

    print("\n" + "="*60)
    print("Probe complete.")
    print("SUMMARY:")
    print("  On Windows, the original test helper will fail because")
    print("  str(WindowsPath).endswith('/.git') is False (uses backslashes).")
    print("  The fix using self.name == '.git' works because Path.name")
    print("  extracts the final component regardless of separator.")