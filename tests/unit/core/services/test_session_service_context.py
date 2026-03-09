from pathlib import Path
from teddy_executor.core.services.session_service import SessionService


def test_resolve_context_paths_finds_session_and_turn_context(tmp_path, monkeypatch):
    # Setup session structure: .teddy/sessions/my-session/01/plan.md
    session_dir = tmp_path / ".teddy" / "sessions" / "my-session"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    plan_path = turn_dir / "plan.md"
    plan_path.touch()

    session_context = session_dir / "session.context"
    session_context.write_text("file1.md", encoding="utf-8")

    turn_context = turn_dir / "turn.context"
    turn_context.write_text("file2.md", encoding="utf-8")

    from unittest.mock import MagicMock

    fsm = MagicMock()
    fsm.read_file.side_effect = lambda p: Path(p).read_text(encoding="utf-8")
    # Initialize service with mocks (not needed for this specific path logic if it's pure)
    service = SessionService(file_system_manager=fsm)

    # Execute
    paths = service.resolve_context_paths(str(plan_path))

    # Assert
    assert paths["Session"] == ["file1.md"]
    assert paths["Turn"] == ["file2.md"]


def test_resolve_context_paths_handles_missing_files(tmp_path):
    # Mock fsm raising FileNotFoundError for missing files
    from unittest.mock import MagicMock

    fsm = MagicMock()
    fsm.read_file.side_effect = FileNotFoundError()

    service = SessionService(fsm)
    paths = service.resolve_context_paths(".teddy/sessions/my-session/01/plan.md")

    assert paths["Session"] == []
    assert paths["Turn"] == []
