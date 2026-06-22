"""Unit tests for session_cli_handlers background check wiring."""

from pathlib import Path


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
