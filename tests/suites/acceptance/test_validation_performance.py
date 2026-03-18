import time
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_validation_performance_on_large_file(tmp_path, monkeypatch):
    """Scenario: Validating an EDIT on a 500-line file should be fast (< 500ms).."""
    # 1. Setup Environment
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 2. Create a large file (500 lines)
    lines = [f"line {i}" for i in range(500)]
    large_content = "\n".join(lines)
    (tmp_path / "large.txt").write_text(large_content, encoding="utf-8")

    # 3. Prepare an EDIT plan for the middle of the file
    find_content = "line 250\nline 251"
    replace_content = "line 250 - modified\nline 251 - modified"
    plan = (
        MarkdownPlanBuilder("Performance Test")
        .add_edit("large.txt", find_content, replace_content)
        .build()
    )

    # 4. Measure execution time
    # Note: This includes CLI startup and DI overhead, but validation is the bulk
    start_time = time.perf_counter()
    result = adapter.run_execute_with_plan(plan, interactive=False)
    duration = time.perf_counter() - start_time

    assert result.exit_code == 0
    assert "SUCCESS" in result.stdout
    # Performance requirement: < 500ms for pre-flight validation on 500 lines
    PERFORMANCE_SLA_SECONDS = 0.5
    assert duration < PERFORMANCE_SLA_SECONDS, (
        f"Validation took too long: {duration:.2f}s"
    )
