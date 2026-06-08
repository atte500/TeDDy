from pathlib import Path
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_start_command_accepts_context_and_overrides(tmp_path: Path, monkeypatch):
    # Arrange
    TestEnvironment(
        monkeypatch, tmp_path
    ).setup().with_real_shell().with_real_filesystem().with_real_init_service()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Create a dummy file to use as additional context
    extra_file = tmp_path / "extra.py"
    extra_file.write_text("# extra context")

    # Act
    # We use -a (agent), -m (message), -c (context), and LLM overrides
    result = adapter.run_cli_command(
        [
            "start",
            "custom-session-name",
            "-a",
            "developer",
            "-m",
            "Test initial message",
            "-c",
            str(extra_file),
            "--model",
            "gpt-4",
            "--provider",
            "openai",
            "--api-key",
            "sk-test-key",
        ],
        input="n\n",
    )

    # Assert (This will fail initially as flags are not wired)
    assert result.exit_code == 0

    # Verify the session was created
    sessions_path = tmp_path / ".teddy/sessions"
    session_dirs = [
        d
        for d in sessions_path.iterdir()
        if d.is_dir() and "custom-session-name" in d.name
    ]
    assert session_dirs, (
        f"Session directory not found in {sessions_path}. Found: {list(sessions_path.iterdir())}"
    )
    session_root = session_dirs[0]

    # Verify session.context includes the extra file
    session_context = (session_root / "session.context").read_text()
    assert str(extra_file) in session_context

    # Verify meta.yaml includes overrides
    # We check Turn 01's meta.yaml for persistence of overrides if they are turn-scoped,
    # or session-level if they are session-scoped. PlanningService should use them.
    import yaml

    meta_file = session_root / "01" / "meta.yaml"
    assert meta_file.exists()
    meta_data = yaml.safe_load(meta_file.read_text())

    assert meta_data.get("model") == "test-model"
    assert meta_data.get("provider") == "openai"
    assert meta_data.get("api_key") == "sk-test-key"

    # Verify additional context was merged into session.context
    session_context_file = session_root / "session.context"
    assert session_context_file.exists()
    content = session_context_file.read_text()
    assert str(extra_file) in content, "Additional context missing from session.context"

    # Verify overrides were persisted in meta.yaml
    meta_file = session_root / "01" / "meta.yaml"
    assert meta_file.exists()
    meta_content = meta_file.read_text()
    assert "model: test-model" in meta_content
    assert "provider: openai" in meta_content
    assert "api_key: sk-test-key" in meta_content


def test_start_command_short_flags_aliases(tmp_path: Path, monkeypatch):
    # This test specifically checks the aliases -a and -c
    TestEnvironment(monkeypatch, tmp_path).setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    result = adapter.run_cli_command(["start", "--help"])

    # Typer/Rich formatting can insert spaces/newlines/boxes, so we check for flag presence
    assert "--agent" in result.stdout
    assert "-a" in result.stdout
    assert "--context" in result.stdout
    assert "-c" in result.stdout
