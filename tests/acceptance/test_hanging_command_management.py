from .helpers import run_execute_with_plan_content
from .plan_builder import MarkdownPlanBuilder


def test_global_timeout_enforcement(monkeypatch, tmp_path):
    """
    Scenario 1: Configurable Global Timeout
    Verifies that a command exceeding the global timeout defined in config is terminated.
    """
    # 1. Setup a local config with a very short timeout
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    config_file = teddy_dir / "config.yaml"
    config_file.write_text(
        "execution:\n  default_timeout_seconds: 0.1\n", encoding="utf-8"
    )

    # 2. Define a plan with a command that takes longer than 0.1 second
    builder = MarkdownPlanBuilder("Hanging Plan")
    builder.add_action(
        "EXECUTE",
        params={"Description": "Run a command that hangs."},
        content_blocks={"COMMAND": ("shell", "sleep 0.5")},
    )
    plan_content = builder.build()

    # 3. Execute the plan.
    result = run_execute_with_plan_content(monkeypatch, plan_content, tmp_path)

    # 4. Assertions
    assert "timed out" in result.stdout.lower()
    assert result.exit_code != 0
