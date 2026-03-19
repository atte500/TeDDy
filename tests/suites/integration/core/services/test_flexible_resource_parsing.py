import pytest
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    """Fixture providing a CliTestAdapter anchored to a temporary workspace."""
    TestEnvironment(monkeypatch, workspace=tmp_path).setup()
    return CliTestAdapter(monkeypatch, cwd=tmp_path)


def test_read_action_supports_file_path_alias(adapter, tmp_path):
    """Scenario: READ action supports the 'File Path' alias."""
    test_file = tmp_path / "test_read_alias.txt"
    test_file.write_text("hello world", encoding="utf-8")

    plan_content = (
        MarkdownPlanBuilder("Alias Test")
        .add_read(
            resource="test_read_alias.txt",
            description="Read the test file",
            key="File Path",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)

    assert result.exit_code == 0
    assert "hello world" in result.stdout


def test_read_action_fails_when_url_provided_in_file_path_alias(adapter):
    """Scenario: READ fails when a URL is provided to the 'File Path' alias."""
    # We pass a raw link string to test the URL constraint bypass
    plan_content = (
        MarkdownPlanBuilder("URL Constraint Test")
        .add_read(
            resource="[www.google.com](https://www.google.com)",
            description="Try to read a URL as a file path",
            key="File Path",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)

    assert result.exit_code != 0
    assert "Strict Local Only" in result.stdout


def test_prune_action_supports_file_path_alias(adapter, tmp_path):
    """Scenario: PRUNE action supports the 'File Path' alias."""
    # We need a file in the environment for validation (even if mocked FS, the path must exist)
    (tmp_path / "README.md").write_text("context content", encoding="utf-8")

    plan_content = (
        MarkdownPlanBuilder("PRUNE Alias Test")
        .add_prune(
            resource="README.md",
            description="Prune the README",
            key="File Path",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)

    # Use the Observer pattern if needed, or check stdout for the action header
    assert "### `PRUNE`: [README.md](/README.md)" in result.stdout


def test_prune_action_fails_when_url_provided_in_file_path_alias(adapter):
    """Scenario: PRUNE fails when a URL is provided to the 'File Path' alias."""
    plan_content = (
        MarkdownPlanBuilder("PRUNE URL Constraint Test")
        .add_prune(
            resource="[www.google.com](https://www.google.com)",
            description="Try to prune a URL",
            key="File Path",
        )
        .build()
    )

    result = adapter.run_execute_with_plan(plan_content)

    assert result.exit_code != 0
    assert "Strict Local Only" in result.stdout
