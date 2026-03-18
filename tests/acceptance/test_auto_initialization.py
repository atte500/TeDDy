from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter


def test_first_time_initialization_creates_teddy_directory_and_files(
    tmp_path, monkeypatch
):
    """Scenario: First-time initialization of the .teddy directory."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # When
    result = adapter.run_command(["context", "--no-copy"])

    # Then
    assert result.exit_code == 0

    teddy_dir = tmp_path / ".teddy"
    config_file = teddy_dir / "config.yaml"
    init_context_file = teddy_dir / "init.context"

    assert teddy_dir.is_dir(), ".teddy directory should be created"
    assert config_file.is_file(), "config.yaml should be created"
    assert init_context_file.is_file(), "init.context should be created"

    # Verify default content
    assert "TeDDy Configuration" in config_file.read_text(encoding="utf-8")
    assert "README.md" in init_context_file.read_text(encoding="utf-8")
