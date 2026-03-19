from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_multi_edit_ux_polish(monkeypatch, tmp_path):
    """Scenario: Multi-edit plan with perfect and fuzzy matches shows similarity scores and ndiff markers."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_config()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Set global threshold to 0.8 for fuzzy matching in this test
    (tmp_path / ".teddy").mkdir(exist_ok=True)
    (tmp_path / ".teddy" / "config.yaml").write_text("similarity_threshold: 0.8\n")

    target_file = tmp_path / "code.py"
    target_file.write_text("line_one = 1\nline_two  =  2\n")

    plan = (
        MarkdownPlanBuilder("UX Polish Plan")
        .add_edit(
            "code.py",
            [
                ("line_one = 1", 'line_one = "perfect"'),
                ("line_two = 2", "line_two = 2.0"),
            ],
            description="Apply perfect and fuzzy edits",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")

    assert result.exit_code == 0
    report = result.stdout

    # 1. Similarity Scores should show both
    assert "**Similarity Scores:** 1.00, 0.89" in report

    # 2. Check for ndiff markers
    assert "?" in report  # Character level marker
    assert "- line_two  =  2" in report
    assert "+ line_two = 2.0" in report

    # 3. Check whitespace (#### diff should be preceded by a newline)
    assert "#### `diff`" in report
    assert "\n#### `diff`" in report


def test_perfect_edit_suppresses_diff(monkeypatch, tmp_path):
    """Scenario: All edits are 1.0, #### diff should be missing from report."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    target_file = tmp_path / "clean.py"
    target_file.write_text("hello")

    plan = (
        MarkdownPlanBuilder("Perfect Plan")
        .add_edit("clean.py", "hello", "world", description="Perfect edit")
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")
    assert result.exit_code == 0
    assert "#### `diff`" not in result.stdout
    assert "**Similarity Score:** 1.00" in result.stdout
