from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


def test_respects_global_similarity_threshold(tmp_path, monkeypatch):
    """Scenario: Low threshold allows a messy edit to pass."""
    # 1. Setup Environment
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 2. Setup config with low threshold
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir(exist_ok=True)
    (teddy_dir / "config.yaml").write_text(
        "similarity_threshold: 0.8\n", encoding="utf-8"
    )

    # 3. Setup target file
    target_file = tmp_path / "src" / "foo.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    # 4. Create plan with a slightly off 'FIND' block (~0.82 similarity)
    plan = (
        MarkdownPlanBuilder("Low Threshold Test")
        .add_edit(
            "src/foo.py",
            "def greet():\n    return 'hi world'",
            "def hello():\n    return 'universe'",
        )
        .build()
    )

    # 5. Execute - should pass because 0.82 > 0.8
    result = adapter.run_execute_with_plan(plan, interactive=False)

    assert "Overall Status:** SUCCESS" in result.stdout
    assert "Similarity Score:** 0.82" in result.stdout
    assert "def hello():\n    return 'universe'" in target_file.read_text(
        encoding="utf-8"
    )


def test_fallback_to_default_threshold(tmp_path, monkeypatch):
    """Scenario: Defaults to 0.95 if not configured."""
    # 1. Setup Environment
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # 2. Setup target file
    target_file = tmp_path / "src" / "foo.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("def hello():\n    return 'world'\n", encoding="utf-8")

    # 3. Create plan with ~0.82 similarity
    plan = (
        MarkdownPlanBuilder("Default Threshold Test")
        .add_edit(
            "src/foo.py",
            "def greet():\n    return 'hi world'",
            "def hello():\n    return 'universe'",
        )
        .build()
    )

    # 4. Execute - should fail because 0.82 < 0.95
    result = adapter.run_execute_with_plan(plan, interactive=False)

    assert "Validation Failed" in result.stdout
    assert "Similarity Threshold:** 0.95" in result.stdout
    assert "def hello():\n    return 'world'" in target_file.read_text(encoding="utf-8")
