import textwrap
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.setup.mocking import POSIXPathMock
from teddy_executor.core.ports.outbound import IConfigService, IWebSearcher
from teddy_executor.adapters.outbound.web_searcher_adapter import WebSearcherAdapter
from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_report_prunes_redundant_sections(tmp_path, monkeypatch):
    """
    Scenario: Execution report prunes redundant sections (Rationale, Original Plan)
    - Given an ExecutionReport resulting from a plan execution.
    - When the report is formatted for Markdown output.
    - Then the output MUST NOT contain the original plan's Rationale section.
    - And the output MUST contain the full, verbatim content of the successful actions.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Setup files
    existing_file = tmp_path / "existing.txt"
    existing_file.write_text("Verbatim content", encoding="utf-8")

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
This is the original rationale that should be hidden.
````

## Action Plan
### `READ`
- **Resource:** existing.txt
"""
    # Execute plan.
    result = runner.invoke(
        app, ["execute", "-y", "--no-copy", "--plan-content", plan_content]
    )

    assert result.exit_code == 0

    # Verify Rationale is NOT present
    assert "original rationale" not in result.stdout.lower()

    # Verify READ content is present
    assert "Verbatim content" in result.stdout

    # Verify Action Log is present
    assert "Action Log" in result.stdout
    assert "READ" in result.stdout
    assert "SUCCESS" in result.stdout


def test_research_report_includes_hint_and_hides_raw_details(tmp_path, monkeypatch):
    """
    Scenario: RESEARCH action report formatting
    - Given a successful RESEARCH action.
    - When the report is rendered.
    - Then the output MUST contain the READ hint.
    - And the output MUST NOT contain the raw query_results in details.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    plan_content = textwrap.dedent("""\
        # Research Plan
        - **Status:** Green 🟢
        - **Agent:** Pathfinder

        ## Rationale
        ~~~~~~text
        I need to find some teddy bears.
        ~~~~~~

        ## Action Plan
        ### `RESEARCH`
        - **Description:** Looking for stuff
        ~~~~~~text
        teddy cli
        ~~~~~~
    """)

    mock_results = [
        {
            "title": "Teddy",
            "href": "https://teddy.com",
            "body": "A cute bear.",
        }
    ]

    # Arrange DI swap
    env = TestEnvironment(monkeypatch, workspace=tmp_path).setup()
    mock_instance = POSIXPathMock()
    mock_instance.text.return_value = iter(mock_results)
    mock_factory = POSIXPathMock()
    mock_factory.return_value.__enter__.return_value = mock_instance

    # Register adapter with injected mock factory
    env.container.register(
        IWebSearcher,
        factory=lambda: WebSearcherAdapter(
            config_service=env.container.resolve(IConfigService),
            ddgs_factory=mock_factory,
        ),
    )

    # Execute plan.
    result = runner.invoke(
        app, ["execute", "-y", "--no-copy", "--plan-content", plan_content]
    )

    assert result.exit_code == 0
    # Verify Hint is present (including backticks from template)
    assert (
        "**Hint:** NOW you MUST use READ on the most promising results" in result.stdout
    )
    # Verify snippets are rendered
    assert "A cute bear." in result.stdout
    # Verify raw details are suppressed
    assert "query_results" not in result.stdout


def test_session_report_is_comprehensive(tmp_path, monkeypatch):
    """
    Scenario: Session Report (Comprehensive) focuses on audit trail
    - Verified via unit tests of the formatter as the CLI session logic is not yet fully wired.
    """
    pass
