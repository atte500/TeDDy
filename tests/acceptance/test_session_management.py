from typer.testing import CliRunner
import yaml
from teddy_executor.__main__ import app

runner = CliRunner()


def test_teddy_new_bootstraps_session(tmp_path, monkeypatch):
    """
    Scenario: teddy new bootstraps a session
    Given no existing session named "feat-x".
    When I run teddy new feat-x.
    Then a directory .teddy/sessions/feat-x/01/ MUST be created.
    And .teddy/sessions/feat-x/session.context MUST exist and contain the content of .teddy/init.context.
    And 01/system_prompt.xml MUST be populated with the default agent prompt.
    And 01/meta.yaml MUST contain a valid turn_id and creation_timestamp.
    """
    # Arrange
    # Change CWD to tmp_path to isolate filesystem side effects
    monkeypatch.chdir(tmp_path)

    # Pre-seed init.context as per specification
    init_context_content = "README.md\ndocs/project/PROJECT.md"
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    (teddy_dir / "init.context").write_text(init_context_content, encoding="utf-8")

    # Seed default prompt and .git to simulate project root
    (tmp_path / ".git").mkdir()
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder prompt</prompt>", encoding="utf-8"
    )

    # Act
    result = runner.invoke(app, ["new", "feat-x"])

    # Assert
    assert result.exit_code == 0

    session_dir = teddy_dir / "sessions" / "feat-x"
    turn_dir = session_dir / "01"

    assert turn_dir.is_dir()

    # Check session.context
    session_context = session_dir / "session.context"
    assert session_context.exists()
    assert session_context.read_text(encoding="utf-8").strip() == init_context_content

    # Check system_prompt.xml
    # Note: We assume 'pathfinder' is the default agent as per spec
    system_prompt = turn_dir / "system_prompt.xml"
    assert system_prompt.exists()
    assert "Pathfinder" in system_prompt.read_text(encoding="utf-8")

    # Check meta.yaml
    meta_file = turn_dir / "meta.yaml"
    assert meta_file.exists()
    with open(meta_file, "r", encoding="utf-8") as f:
        meta_data = yaml.safe_load(f)
        assert "turn_id" in meta_data
        assert "creation_timestamp" in meta_data
        assert meta_data["turn_id"] == "01"
