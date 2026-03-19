from teddy_executor.core.ports.outbound.session_manager import ISessionManager


def test_resolve_context_paths_finds_session_and_turn_context(env):
    """
    Verify that resolve_context_paths correctly identifies and reads
    session.context and turn.context relative to the plan path.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    plan_path = ".teddy/sessions/my-session/01/plan.md"
    session_context_path = ".teddy/sessions/my-session/session.context"
    turn_context_path = ".teddy/sessions/my-session/01/turn.context"

    valid_paths = {session_context_path, turn_context_path}
    mock_fs.path_exists.side_effect = lambda p: p in valid_paths
    mock_fs.read_file.side_effect = lambda p: {
        session_context_path: "file1.md",
        turn_context_path: "file2.md",
    }.get(p, "")

    # Act
    paths = service.resolve_context_paths(plan_path)

    # Assert
    assert paths["Session"] == ["file1.md"]
    assert paths["Turn"] == ["file2.md"]


def test_resolve_context_paths_handles_missing_files(env):
    """
    Verify that resolve_context_paths returns empty lists when context files are missing.
    """
    # Arrange
    service = env.get_service(ISessionManager)
    mock_fs = env.get_mock_filesystem()

    # Repository returns empty set if path_exists is False
    mock_fs.path_exists.return_value = False

    # Act
    paths = service.resolve_context_paths(".teddy/sessions/my-session/01/plan.md")

    # Assert
    assert paths["Session"] == []
    assert paths["Turn"] == []
