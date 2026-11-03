"""Workspace verbosity: a silenced helper still performs its repair.

Slice 00-12 Core deliverable. With ``verbose=False`` each helper must emit
nothing while still running its repair side effect. The default
``verbose=True`` keeps every line intact, and ``_run_health_checks`` forwards
the flag to both helpers.
"""

import subprocess

from teddy_executor.adapters.inbound import session_cli_handlers as handlers

PRE_COMMIT_INSTALL_ARGV = [
    "pre-commit",
    "install",
    "-f",
    "-t",
    "pre-commit",
    "-t",
    "post-commit",
]


def _record_run(monkeypatch) -> list[list[str]]:
    """Record every ``subprocess.run`` command and succeed without spawning.

    A ``CompletedProcess`` with no ``stdout`` makes ``_resolve_hooks_dir``
    return ``None`` (unresolvable), so the pre-commit path falls through to a
    real install call, which is exactly the repair under test.
    """
    calls: list[list[str]] = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, returncode=0)

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        fake_run,
    )
    return calls


def test_ensure_commit_hooks_verbose_false_silences_but_still_installs(
    monkeypatch, capsys
):
    """A silenced hook repair prints nothing yet still runs the install."""
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.shutil.which",
        lambda name: "/fake/pre-commit" if name == "pre-commit" else None,
    )
    calls = _record_run(monkeypatch)

    handlers._ensure_commit_hooks(verbose=False)

    assert capsys.readouterr().err == ""
    assert PRE_COMMIT_INSTALL_ARGV in calls


def test_ensure_commit_hooks_default_verbose_prints_the_green_line(monkeypatch, capsys):
    """The default verbosity keeps the green confirmation."""
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.shutil.which",
        lambda name: "/fake/pre-commit" if name == "pre-commit" else None,
    )
    _record_run(monkeypatch)

    handlers._ensure_commit_hooks()

    assert "pre-commit hooks installed" in capsys.readouterr().err


def test_check_git_initialized_verbose_false_silences_but_still_initializes(
    monkeypatch, capsys
):
    """A silenced git check prints nothing yet still runs ``git init``."""
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.shutil.which",
        lambda name: "/usr/bin/git",
    )

    def controlled_exists(self):
        return False if self.name == ".git" else True

    monkeypatch.setattr("pathlib.Path.exists", controlled_exists)
    calls = _record_run(monkeypatch)

    handlers._check_git_initialized(verbose=False)

    assert capsys.readouterr().err == ""
    assert ["git", "init"] in calls


def test_check_git_initialized_verbose_false_silences_the_warning(monkeypatch, capsys):
    """A silenced git check hides even the missing-CLI warning."""
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.shutil.which",
        lambda name: None,
    )

    handlers._check_git_initialized(verbose=False)

    assert capsys.readouterr().err == ""


def test_run_health_checks_forwards_verbose_to_both_helpers(monkeypatch):
    """``_run_health_checks`` passes ``verbose`` through to each helper."""
    received: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        handlers, "_ensure_commit_hooks", lambda **kw: received.append(("hooks", kw))
    )
    monkeypatch.setattr(
        handlers, "_check_git_initialized", lambda **kw: received.append(("init", kw))
    )

    class _EnabledConfig:
        def get_setting(self, key, default=None):
            return default

    handlers._run_health_checks(_EnabledConfig(), verbose=False)

    assert received == [
        ("hooks", {"verbose": False}),
        ("init", {"verbose": False}),
    ]
