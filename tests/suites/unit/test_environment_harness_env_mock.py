"""Unit tests for the harness ``ISystemEnvironment`` mock's TTY signal.

The one-time editor-setup gate (Slice 00-26) keys on a terminal-availability
signal, so the harness must give its auto-specced ``ISystemEnvironment`` double
a DETERMINISTIC ``isatty()`` default (``False``). An unconfigured auto-specced
``isatty()`` returns a truthy ``MagicMock``, which would make every
CLI-driving test look as though it runs on a TTY. The ``with_tty(value)``
toggle lets behavioural tests opt into TTY-on / TTY-off explicitly.
"""

from teddy_executor.core.ports.outbound import ISystemEnvironment

from tests.harness.setup.test_environment import TestEnvironment


def test_harness_env_mock_defaults_isatty_to_false(monkeypatch):
    """An unconfigured env double must report a NON-TTY (``False``)."""
    env = TestEnvironment(monkeypatch)
    try:
        env.setup()
        mock_env = env.get_service(ISystemEnvironment)

        assert mock_env.isatty() is False
    finally:
        env.teardown()


def test_harness_env_mock_with_tty_true_enables_tty(monkeypatch):
    """``with_tty(True)`` forces the env double to report a TTY."""
    env = TestEnvironment(monkeypatch)
    try:
        env.setup()
        env.with_tty(True)
        mock_env = env.get_service(ISystemEnvironment)

        assert mock_env.isatty() is True
    finally:
        env.teardown()


def test_harness_env_mock_with_tty_false_disables_tty(monkeypatch):
    """``with_tty(False)`` forces the env double to report a NON-TTY."""
    env = TestEnvironment(monkeypatch)
    try:
        env.setup()
        env.with_tty(True)
        env.with_tty(False)
        mock_env = env.get_service(ISystemEnvironment)

        assert mock_env.isatty() is False
    finally:
        env.teardown()
