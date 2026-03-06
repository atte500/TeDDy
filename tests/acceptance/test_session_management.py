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


def test_teddy_context_aggregates_cascading_context(tmp_path, monkeypatch):
    """
    Scenario: teddy context aggregates cascading context
    Given a session with "file_a.py" in session.context and "file_b.py" in 01/turn.context.
    When I run teddy context inside the 01/ directory.
    Then the generated output MUST contain the contents of both "file_a.py" and "file_b.py".
    And "file_b.py" MUST be listed under the "Turn" section of the Context Summary.
    """
    # Arrange
    monkeypatch.chdir(tmp_path)

    # 1. Setup project files
    (tmp_path / "file_a.py").write_text("content_a", encoding="utf-8")
    (tmp_path / "file_b.py").write_text("content_b", encoding="utf-8")

    # 2. Setup session directory structure
    session_dir = tmp_path / ".teddy" / "sessions" / "feat-x"
    turn_dir = session_dir / "01"
    turn_dir.mkdir(parents=True)

    # 3. Create context files and metadata
    (session_dir / "session.context").write_text("file_a.py", encoding="utf-8")
    (turn_dir / "turn.context").write_text("file_b.py", encoding="utf-8")
    (turn_dir / "meta.yaml").write_text("turn_id: '01'\n", encoding="utf-8")

    # Change CWD to the turn directory to simulate user being 'inside' it
    monkeypatch.chdir(turn_dir)

    # Act
    # We use --no-copy to avoid polluting clipboard during tests
    result = runner.invoke(app, ["context", "--no-copy"])

    # Assert
    assert result.exit_code == 0

    # Check that both files are present in the output
    assert "content_a" in result.stdout
    assert "content_b" in result.stdout

    # Check Context Summary section (Requirement from specification)
    # The specification says the output format for session/turn should be clear.
    # Note: Our current ContextService doesn't have 'Turn' vs 'Session' headings yet.
    # This test will drive that change.
    assert "### Turn" in result.stdout
    assert "file_b.py" in result.stdout
    assert "### Session" in result.stdout
    assert "file_a.py" in result.stdout
