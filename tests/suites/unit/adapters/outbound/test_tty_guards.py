import sys
import importlib
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture
def mock_termios():
    # Force removal of real termios and inject our mock.
    if "termios" in sys.modules:
        del sys.modules["termios"]

    mock_m = MagicMock()
    mock_m.tcgetattr.return_value = [0] * 7
    mock_m.TCSAFLUSH = 2
    mock_m.ICRNL = 256
    mock_m.ICANON = 2
    mock_m.ECHO = 8
    mock_m.ISIG = 1
    mock_m.IEXTEN = 1024

    with patch.dict("sys.modules", {"termios": mock_m}):
        # Force reloads of SUT modules to ensure they pick up the mock on the next 'import termios' call.
        if "teddy_executor.adapters.outbound.system_environment_adapter" in sys.modules:
            importlib.reload(
                sys.modules[
                    "teddy_executor.adapters.outbound.system_environment_adapter"
                ]
            )
        if "teddy_executor.adapters.outbound.console_interactor_helpers" in sys.modules:
            importlib.reload(
                sys.modules[
                    "teddy_executor.adapters.outbound.console_interactor_helpers"
                ]
            )
        yield mock_m


def test_system_environment_adapter_run_command_guards_tty(monkeypatch, mock_termios):
    """
    Ensure SystemEnvironmentAdapter.run_command does NOT attempt
    to restore TTY state during tests, preventing SIGTTOU hangs.
    """
    from teddy_executor.adapters.outbound.system_environment_adapter import (
        SystemEnvironmentAdapter,
    )

    adapter = SystemEnvironmentAdapter()

    monkeypatch.setattr("sys.platform", "linux")

    # PART 1: Verify it WOULD call tcsetattr if the guard were missing (Buggy State)
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdin.fileno", return_value=0),
        patch("subprocess.run"),
    ):
        # We simulate the buggy state by removing the env var
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        adapter.run_command(["ls"])
        assert mock_termios.tcsetattr.called, (
            "Test Setup Error: tcsetattr was NOT called."
        )

    # PART 2: Verify the guard prevents the call (Fixed State)
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdin.fileno", return_value=0),
        patch("subprocess.run"),
    ):
        mock_termios.tcsetattr.reset_mock()
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tty_guards")
        adapter.run_command(["ls"])

        assert not mock_termios.tcsetattr.called, (
            "VULNERABILITY DETECTED: SystemEnvironmentAdapter.run_command "
            "attempted tcsetattr during a test run."
        )


def test_restore_terminal_mode_guards_tty(monkeypatch, mock_termios):
    """
    Ensure console_interactor_helpers.restore_terminal_mode does NOT attempt
    to restore TTY state during tests.
    """
    from teddy_executor.adapters.outbound.console_interactor_helpers import (
        restore_terminal_mode,
    )

    monkeypatch.setattr("sys.platform", "linux")

    # PART 1: Buggy State
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdin.fileno", return_value=0),
    ):
        monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
        restore_terminal_mode()
        assert mock_termios.tcsetattr.called, (
            "Test Setup Error: tcsetattr was NOT called."
        )

    # PART 2: Fixed State
    with (
        patch("sys.stdin.isatty", return_value=True),
        patch("sys.stdin.fileno", return_value=0),
    ):
        mock_termios.tcsetattr.reset_mock()
        monkeypatch.setenv("PYTEST_CURRENT_TEST", "test_tty_guards")
        restore_terminal_mode()

        assert not mock_termios.tcsetattr.called, (
            "VULNERABILITY DETECTED: restore_terminal_mode "
            "attempted tcsetattr during a test run."
        )
