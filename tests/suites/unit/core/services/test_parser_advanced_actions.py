import pytest

from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder


@pytest.fixture
def parser(container) -> IPlanParser:
    """Resolves the MarkdownPlanParser from the container."""
    return container.resolve(IPlanParser)


def test_parse_execute_action(parser: IPlanParser):
    """Verify parsing of EXECUTE action with metadata."""
    # Arrange
    builder = MarkdownPlanBuilder("Execute a command").add_execute(
        command="poetry run pytest",
        description="Run the test suite.",
        expected_outcome="All tests will pass.",
        cwd="/tmp/tests",
        env={"API_KEY": "secret", "DEBUG": "1"},
    )

    # Act
    result_plan = parser.parse(builder.build())

    # Assert
    assert len(result_plan.actions) == 1
    action = result_plan.actions[0]
    assert action.type == "EXECUTE"
    assert action.description == "Run the test suite."
    assert action.params["command"] == "poetry run pytest"
    assert action.params["expected_outcome"] == "All tests will pass."
    assert action.params["cwd"] == "/tmp/tests"
    assert action.params["env"] == {"API_KEY": "secret", "DEBUG": "1"}


def test_parse_execute_action_with_colon(parser: IPlanParser):
    """Verify that a command with a colon is parsed correctly."""
    builder = MarkdownPlanBuilder("Test Execute Action").add_execute(
        command="echo hello:world", description="Run a command with a colon."
    )
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["command"] == "echo hello:world"


def test_parse_research_action(parser: IPlanParser):
    """Verify parsing of RESEARCH action."""
    builder = MarkdownPlanBuilder("Research a topic").add_research(
        queries=[
            "python markdown ast library",
            "  multi-line within block",
            "another block query",
        ],
        description="Find libraries for parsing Markdown.",
    )
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["queries"] == [
        "python markdown ast library",
        "multi-line within block",
        "another block query",
    ]


def test_parse_prompt_action(parser: IPlanParser):
    """Verify parsing of PROMPT action."""
    prompt_text = "This is the first paragraph of the prompt.\n\nThis is the second paragraph, with some `inline_code`."
    builder = MarkdownPlanBuilder("Chat with the user").add_prompt(prompt_text)
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["prompt"] == prompt_text


def test_parse_prompt_action_with_reference_files(parser: IPlanParser):
    """Verify extraction of reference files in PROMPT."""
    builder = MarkdownPlanBuilder("Chat with the user").add_prompt(
        message="Please look at this file.", reference_files=["important.txt"]
    )
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["handoff_resources"] == ["important.txt"]
    assert result_plan.actions[0].params["prompt"] == "Please look at this file."


def test_parse_prune_action(parser: IPlanParser):
    """Verify parsing of PRUNE action."""
    builder = MarkdownPlanBuilder("Prune resource").add_prune(
        resource="docs/project/specs/old-spec.md",
        description="Remove the old specification.",
    )
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["resource"] == "docs/project/specs/old-spec.md"


def test_parse_invoke_action(parser: IPlanParser):
    """Verify parsing of INVOKE action."""
    builder = MarkdownPlanBuilder("Invoke agent").add_invoke(
        agent="Architect",
        description="Handoff to the Architect.",
        reference_files=["docs/briefs/new-feature.md"],
    )
    result_plan = parser.parse(builder.build())
    action = result_plan.actions[0]
    assert action.params["agent"] == "Architect"
    assert action.params["handoff_resources"] == ["docs/briefs/new-feature.md"]
    assert action.params["message"] == "Handoff to the Architect."


def test_parse_return_action(parser: IPlanParser):
    """Verify parsing of RETURN action."""
    builder = MarkdownPlanBuilder("Conclude sub-task").add_return(
        description="My analysis is complete.",
        reference_files=["docs/rca/the-bug.md", "spikes/fix-script.sh"],
    )
    result_plan = parser.parse(builder.build())
    action = result_plan.actions[0]
    assert action.params["handoff_resources"] == [
        "docs/rca/the-bug.md",
        "spikes/fix-script.sh",
    ]
    assert action.params["message"] == "My analysis is complete."


def test_parser_accepts_multiline_execute(parser: IPlanParser):
    """Verify parser preserves multiline commands in EXECUTE."""
    cmd = 'echo "hello"\necho "world"'
    builder = MarkdownPlanBuilder("Execute multiline").add_execute(cmd)
    result_plan = parser.parse(builder.build())
    assert result_plan.actions[0].params["command"] == cmd
