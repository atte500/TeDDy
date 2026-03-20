import textwrap
from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def test_parser_highlights_multiple_structural_mismatches(tmp_path, monkeypatch):
    """
    Scenario: Multi-Highlight AST Mismatches
    Given a plan with multiple structural errors (missing metadata list AND wrong heading level)
    When the plan is executed
    Then the CLI should output the AST summary with highlights on all offending nodes.
    """
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    malformed_plan = textwrap.dedent("""\
        # A Malformed Plan
        This is a paragraph instead of a list.
        ### Wrong Heading Level (Rationale)
        ```text
        Some rationale
        ```
        ## Action Plan
    """)

    result = adapter.run_command(["execute", "--plan-content", malformed_plan])

    assert result.exit_code != 0
    output = result.stdout

    # Ensure the AST summary is present
    assert "### Actual Response Structure" in output

    # Extract the structure section for focused assertions
    structure_section = output.split("### Actual Response Structure")[-1]

    # We expect highlights on the paragraph (Node 1) and the H3 heading (Node 2)
    assert "[✗] [001] Paragraph" in structure_section
    assert 'Paragraph: "This is a paragraph instead of a list."' in structure_section
    assert 'Heading (Level 3): "Wrong Heading Level (Rationale)"' in structure_section
    assert "(Error: " in structure_section


def test_parser_highlights_multiple_mismatches_in_action_plan(tmp_path, monkeypatch):
    """
    Scenario: Multi-Highlight AST Mismatches (Action Plan)
    Given a plan with multiple structural errors inside the Action Plan section
    When the plan is executed
    Then the CLI should output highlights for offending nodes.
    """
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    malformed_plan = textwrap.dedent("""\
        # Valid Title
        - Status: Green
        - Agent: Pathfinder

        ## Rationale
        ```text
        Valid rationale
        ```

        ## Action Plan
        ### `EXECUTE`
        - Description: Valid
        ```shell
        ls
        ```
        This is an invalid paragraph.
        ### `CREATE`
        - File Path: /tmp/test
        - Description: Valid
        ```text
        content
        ```
        This is another invalid paragraph.
    """)

    result = adapter.run_command(["execute", "--plan-content", malformed_plan])
    assert result.exit_code != 0
    structure_section = result.stdout.split("### Actual Response Structure")[-1]

    assert 'Paragraph: "This is an invalid paragraph."' in structure_section
    assert "[✗]" in structure_section


def test_parser_truncates_long_paragraphs_in_ast(tmp_path, monkeypatch):
    """Scenario: Parser truncates long paragraphs in AST summary for readability."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    long_msg = "This is a very long paragraph that exceeds the sixty character limit to test truncation."
    truncated_msg = long_msg[:60].strip() + "..."

    malformed_plan = textwrap.dedent(f"""\
        # Valid Title
        - Status: Green
        - Agent: Pathfinder

        ## Rationale
        ```text
        Valid rationale
        ```

        ## Action Plan
        {long_msg}
    """)

    result = adapter.run_command(["execute", "--plan-content", malformed_plan])
    assert result.exit_code != 0
    structure_section = result.stdout.split("### Actual Response Structure")[-1]

    assert f'Paragraph: "{truncated_msg}"' in structure_section
    assert "[✗]" in structure_section
