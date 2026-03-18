from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_multi_block_edit_shows_all_diffs(monkeypatch, tmp_path):
    """Scenario: Single EDIT action with two separate FIND/REPLACE blocks shows all diffs and hunks."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Set global threshold to 0.8 for fuzzy matching in this test
    (tmp_path / ".teddy").mkdir(exist_ok=True)
    (tmp_path / ".teddy" / "config.yaml").write_text("similarity_threshold: 0.8\n")

    target_file = tmp_path / "multi_site.py"
    # Large gap to trigger hunk separation
    content = ["site_one  =  1"] + ["# line"] * 10 + ["site_two  =  2"]
    target_file.write_text("\n".join(content) + "\n")

    plan = (
        MarkdownPlanBuilder("Multi-Site Plan")
        .add_edit(
            "multi_site.py",
            [("site_one = 1", "site_one = 1.0"), ("site_two = 2", "site_two = 2.0")],
            description="Edit two sites",
        )
        .build()
    )

    # We need to manually add the Similarity Threshold to the builder output
    # as the builder doesn't have a specific parameter for per-action threshold yet.
    # Alternatively, we rely on the global config we just wrote.

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")
    assert result.exit_code == 0
    report = result.stdout

    # Verify both changes are in the diff
    assert "- site_one  =  1" in report
    assert "+ site_one = 1.0" in report
    assert "- site_two  =  2" in report
    assert "+ site_two = 2.0" in report
    assert "?" in report
    assert "..." in report
