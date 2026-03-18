from pathlib import Path
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.drivers.cli_adapter import CliTestAdapter
from tests.setup.test_environment import TestEnvironment


def test_identical_find_and_replace_blocks_returns_hint(tmp_path: Path, monkeypatch):
    """Scenario: Identical FIND/REPLACE blocks trigger a validation hint."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "app.py").write_text("print('hello')", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Identical Blocks Hint")
        .add_edit("app.py", "print('hello')", "print('hello')")
        .build()
    )

    # Validation failure expected
    report = adapter.execute_plan(plan)

    assert "Validation Failed" in report.stdout
    expected_hint = (
        "FIND and REPLACE blocks are identical. This edit can be safely omitted."
    )
    assert expected_hint in report.stdout


def test_edit_validation_hint_already_applied(tmp_path: Path, monkeypatch):
    """Scenario: Missing FIND but present REPLACE block triggers 'Already Applied' hint."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Content matches REPLACE, not FIND
    (tmp_path / "app.py").write_text(
        "def hello():\n    print('Hello pytest')\n", encoding="utf-8"
    )

    plan = (
        MarkdownPlanBuilder("Already Applied Hint")
        .add_edit(
            "app.py",
            "def hello():\n    print('Hello world')",
            "def hello():\n    print('Hello pytest')",
        )
        .build()
    )

    # Validation failure expected
    report = adapter.execute_plan(plan)

    assert "Validation Failed" in report.stdout
    assert "The `FIND` block could not be located" in report.stdout
    expected_hint = "The FIND block was not found, but the REPLACE block is already present. This change might have already been applied."
    assert expected_hint in report.stdout
