from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_create_fails_if_file_exists_without_overwrite(tmp_path, monkeypatch):
    """Scenario: CREATE validation fails if target file exists and Overwrite is omitted."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Given a file that already exists
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("original content", encoding="utf-8")

    # And a plan with a CREATE action targeting that file without Overwrite: true
    plan = (
        MarkdownPlanBuilder("Test Plan")
        .add_create("existing.txt", "new content")
        .build()
    )

    # When the plan is executed
    result = adapter.run_execute_with_plan(plan, tmp_path)

    # Then validation must fail
    assert result.exit_code != 0

    # And the failure message must hint at the Overwrite parameter
    assert "File already exists: existing.txt" in result.stdout
    assert "Overwrite: true" in result.stdout
