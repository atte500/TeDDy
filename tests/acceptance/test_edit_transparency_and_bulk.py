from tests.setup.test_environment import TestEnvironment
from tests.drivers.cli_adapter import CliTestAdapter
from tests.drivers.plan_builder import MarkdownPlanBuilder


def test_edit_reports_similarity_score_on_success(monkeypatch, tmp_path):
    """Scenario 5.1: Success Transparency reports Similarity Score."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    target_file = tmp_path / "app.py"
    target_file.write_text("print('hello')\n", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Success Transparency")
        .add_edit(
            "app.py", "print('hello')", "print('world')", description="Perfect match"
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")
    assert result.exit_code == 0
    assert "**Similarity Score:** 1.00" in result.stdout
    assert target_file.read_text(encoding="utf-8") == "print('world')\n"


def test_edit_bulk_replacement(monkeypatch, tmp_path):
    """Scenario 5.2: Multi-Instance Replacement with Replace All: true."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    target_file = tmp_path / "multi.py"
    content = "DEBUG: start\nDEBUG: middle\nDEBUG: end\n"
    target_file.write_text(content, encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Bulk Replace")
        .add_edit(
            "multi.py",
            "DEBUG:",
            "INFO:",
            description="Replace all DEBUG logs",
            replace_all=True,
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")
    assert result.exit_code == 0

    # Verify file content
    expected = "INFO: start\nINFO: middle\nINFO: end\n"
    assert target_file.read_text(encoding="utf-8") == expected

    # Verify reporting
    assert "**Similarity Score:** 1.00" in result.stdout
    assert "**Replace All:** True" in result.stdout


def test_edit_ambiguity_hint_update(monkeypatch, tmp_path):
    """Scenario 5.3: Improved Ambiguity Hint on non-bulk edit with multiple matches."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    target_file = tmp_path / "ambiguous.py"
    target_file.write_text("dup\ndup\n", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Ambiguity Hint")
        .add_edit("ambiguous.py", "dup", "changed", description="Ambiguous edit")
        .build()
    )

    result = adapter.run_execute_with_plan(plan, tmp_path, input="y\n")

    # Should fail validation
    assert "The `FIND` block is ambiguous" in result.stdout
    assert (
        "use `Replace All: true` to change all occurrences in the file at once"
        in result.stdout
    )
