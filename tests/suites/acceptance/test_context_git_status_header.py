from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment


def test_context_payload_renders_porcelain_status_in_fence(tmp_path, monkeypatch):
    """Scenario: the payload shows the branch header inside a fenced block."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_filesystem()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / ".teddy").mkdir()
    (tmp_path / ".teddy/init.context").write_text("README.md\n", encoding="utf-8")
    (tmp_path / "README.md").touch()

    mock_inspector = env.get_service(IEnvironmentInspector)
    mock_inspector.get_git_status.return_value = "## main...origin/main"

    result = adapter.run_cli_command(["context"], tmp_path)

    assert result.exit_code == 0
    assert "## Git Status" in result.stdout
    assert "```\n## main...origin/main\n```" in result.stdout
