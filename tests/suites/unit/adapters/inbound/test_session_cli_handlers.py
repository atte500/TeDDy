"""Unit tests for session_cli_handlers background check wiring and health checks."""

from pathlib import Path


def test_ensure_commit_hooks_config_missing(monkeypatch):
    """When .pre-commit-config.yaml does not exist, should show yellow warning."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _ensure_commit_hooks,
    )

    _ensure_commit_hooks()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "No pre-commit hooks configured" in msg
    assert fg == typer.colors.YELLOW
    assert err is True


def test_ensure_commit_hooks_cli_not_found(monkeypatch):
    """When pre-commit CLI not found, should show yellow warning."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _ensure_commit_hooks,
    )

    _ensure_commit_hooks()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "pre-commit CLI not found" in msg
    assert fg == typer.colors.YELLOW
    assert err is True


def test_ensure_commit_hooks_success(monkeypatch):
    """When config exists and CLI is available, should install hooks and show green notification."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/pre-commit")

    # Mock subprocess.run to succeed
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        lambda *args, **kwargs: None,
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _ensure_commit_hooks,
    )

    _ensure_commit_hooks()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "pre-commit hooks installed" in msg
    assert fg == typer.colors.GREEN
    assert err is True


def test_ensure_commit_hooks_failure(monkeypatch):
    """When subprocess.run fails, should log debug and return without notification."""
    import logging

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/pre-commit")

    def fake_run(*args, **kwargs):
        raise __import__("subprocess").CalledProcessError(1, "pre-commit install")

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        fake_run,
    )

    # Silence logging output during test
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.logger",
        logging.getLogger("test"),
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _ensure_commit_hooks,
    )

    _ensure_commit_hooks()

    assert len(messages) == 0, f"Expected 0 secho calls, got {len(messages)}"


def test_check_git_cli_not_found(monkeypatch):
    """When git CLI not found, should show yellow warning."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("shutil.which", lambda cmd: None)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _check_git_initialized,
    )

    _check_git_initialized()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "Git CLI not found" in msg
    assert fg == typer.colors.YELLOW
    assert err is True


def test_check_git_already_repo(monkeypatch):
    """When .git exists in CWD, should show green 'Git repository detected'."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/git")

    # Simulate that (Path.cwd() / ".git").exists() returns True
    monkeypatch.setattr("pathlib.Path.exists", lambda self: True)

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _check_git_initialized,
    )

    _check_git_initialized()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "Git repository detected" in msg
    assert fg == typer.colors.GREEN
    assert err is True


def test_check_git_initialized_success(monkeypatch):
    """When .git missing and git init succeeds, should show green 'Git repository initialized'."""
    import typer

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/git")

    # Simulate that (Path.cwd() / ".git").exists() returns False
    def controlled_exists(self):
        # Only return False for the .git check; let other Path.exists calls pass through
        if self.name == ".git":
            return False
        return True

    monkeypatch.setattr("pathlib.Path.exists", controlled_exists)

    # Mock subprocess.run for git init to succeed
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        lambda *args, **kwargs: type("FakeResult", (), {"returncode": 0})(),
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _check_git_initialized,
    )

    _check_git_initialized()

    assert len(messages) == 1, f"Expected 1 secho call, got {len(messages)}"
    msg, fg, err = messages[0]
    assert "Git repository initialized" in msg
    assert fg == typer.colors.GREEN
    assert err is True


def test_check_git_initialized_failure(monkeypatch):
    """When .git missing and git init fails, should log debug and return without notification."""
    import logging

    messages = []

    def fake_secho(msg, fg=None, err=None):
        messages.append((msg, fg, err))

    monkeypatch.setattr("typer.secho", fake_secho)
    monkeypatch.setattr("shutil.which", lambda cmd: "/usr/bin/git")

    # Simulate that (Path.cwd() / ".git").exists() returns False
    def controlled_exists(self):
        if self.name == ".git":
            return False
        return True

    monkeypatch.setattr("pathlib.Path.exists", controlled_exists)

    # Mock subprocess.run for git init to fail
    def fake_run(*args, **kwargs):
        raise __import__("subprocess").CalledProcessError(128, "git init")

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.subprocess.run",
        fake_run,
    )

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.logger",
        logging.getLogger("test"),
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _check_git_initialized,
    )

    _check_git_initialized()

    assert len(messages) == 0, f"Expected 0 secho calls, got {len(messages)}"


def test_run_health_checks_calls_both(monkeypatch):
    """_run_health_checks should call _ensure_commit_hooks and _check_git_initialized."""
    calls = []

    def fake_commit_hooks():
        calls.append("commit_hooks")

    def fake_git():
        calls.append("git")

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._ensure_commit_hooks",
        fake_commit_hooks,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._check_git_initialized",
        fake_git,
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        _run_health_checks,
    )

    _run_health_checks()

    assert calls == ["commit_hooks", "git"], f"Expected both calls, got {calls}"


def test_handle_new_session_starts_background_check_thread(monkeypatch):
    """Wiring: `handle_new_session` should start a daemon thread
    with target=background_check and the cache path as argument."""
    from threading import Thread as OriginalThread

    # Track Thread constructor calls
    thread_calls = []

    class TrackingThread(OriginalThread):
        def __init__(self, *args, **kwargs):
            thread_calls.append(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("threading.Thread", TrackingThread)

    from unittest.mock import Mock

    mock_container = Mock()
    mock_container.resolve.return_value = Mock()

    # Mock find_project_root to return a predictable path
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.find_project_root",
        lambda: Path("/fake/project"),
    )

    # Mock background_check to avoid real imports
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.background_check",
        lambda cache_path, index_url=None: None,
    )

    # Bypass session orchestration logic to avoid mock container failures
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._run_cli_preflight_check",
        lambda container, agent=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._orchestrate_session_loop",
        lambda container, session_name, interactive, no_copy: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._echo_config_success",
        lambda container, agent=None, model=None, actual_model=None: None,
    )
    # Mock ensure_initialized to a no-op (container.resolve returns a Mock)
    monkeypatch.setattr(
        "teddy_executor.core.ports.inbound.init.IInitUseCase.ensure_initialized",
        lambda self: None,
    )
    # Configure the mock container's ISessionManager.create_session to return
    # a real string so Path(session_dir).name doesn't crash.
    mock_session_manager = Mock()
    mock_session_manager.create_session.return_value = "/fake/session/new"
    mock_container.resolve.side_effect = lambda cls: mock_session_manager

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_new_session,
    )

    handle_new_session(
        container=mock_container,
        name="test_session",
        agent="test_agent",
        interactive=False,
        no_copy=True,
        message="Test",
        additional_context=None,
        model=None,
        provider=None,
        api_key=None,
    )

    assert len(thread_calls) >= 1, (
        f"Expected at least 1 Thread call, got {len(thread_calls)}"
    )
    # Find the thread targeting background_check (there might be other threads)
    bg_thread = None
    for call in thread_calls:
        import teddy_executor.adapters.inbound.session_cli_handlers as handlers

        if call.get("target") is handlers.background_check:
            bg_thread = call
            break

    assert bg_thread is not None, (
        "No Thread call found with target=background_check. "
        f"All Thread calls: {thread_calls}"
    )
    assert bg_thread.get("daemon") is True, f"Expected daemon=True, got {bg_thread}"
    args = bg_thread.get("args", ())
    assert len(args) >= 1, f"Expected at least 1 arg (cache_path), got {args}"
    cache_path = args[0]
    assert isinstance(cache_path, Path), (
        f"Expected cache_path to be a Path, got {type(cache_path)}: {cache_path}"
    )
    assert ".update_cache.json" in str(cache_path), (
        f"Expected cache path to contain '.update_cache.json', got {cache_path}"
    )


def test_handle_resume_session_starts_background_check_thread(monkeypatch):
    """Wiring: `handle_resume_session` should start a daemon thread
    with target=background_check and the cache path as argument."""
    from threading import Thread as OriginalThread

    thread_calls = []

    class TrackingThread(OriginalThread):
        def __init__(self, *args, **kwargs):
            thread_calls.append(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr("threading.Thread", TrackingThread)

    from unittest.mock import Mock

    mock_container = Mock()
    mock_container.resolve.return_value = Mock()

    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.cli_helpers.find_project_root",
        lambda: Path("/fake/project"),
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers.background_check",
        lambda cache_path, index_url=None: None,
    )

    # Bypass session orchestration logic to avoid mock container failures
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._run_cli_preflight_check",
        lambda container, agent=None: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._orchestrate_session_loop",
        lambda container, session_name, interactive, no_copy: None,
    )
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._sync_and_display_session_meta",
        lambda container, session_name, model=None, provider=None, api_key=None: None,
    )
    # Mock _resolve_session_name to return a real string so
    # Path(".teddy") / "sessions" / session_name doesn't crash.
    monkeypatch.setattr(
        "teddy_executor.adapters.inbound.session_cli_handlers._resolve_session_name",
        lambda container, path=None: "test_session",
    )

    from teddy_executor.adapters.inbound.session_cli_handlers import (
        handle_resume_session,
    )

    handle_resume_session(
        container=mock_container,
        path=None,
        interactive=False,
        no_copy=True,
        model=None,
        provider=None,
        api_key=None,
    )

    assert len(thread_calls) >= 1, (
        f"Expected at least 1 Thread call, got {len(thread_calls)}"
    )
    import teddy_executor.adapters.inbound.session_cli_handlers as handlers

    bg_thread = None
    for call in thread_calls:
        if call.get("target") is handlers.background_check:
            bg_thread = call
            break

    assert bg_thread is not None, (
        "No Thread call found with target=background_check. "
        f"All Thread calls: {thread_calls}"
    )
    assert bg_thread.get("daemon") is True
    args = bg_thread.get("args", ())
    assert len(args) >= 1
    cache_path = args[0]
    assert isinstance(cache_path, Path)
    assert ".update_cache.json" in str(cache_path)
