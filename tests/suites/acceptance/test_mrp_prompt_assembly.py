"""Acceptance gate for MRP base prompt injection (MRP Base Prompt slice).

Subcutaneous end-to-end test: drive a real session through the CLI, capture the
system prompt the harness fake LLM receives, and assert it carries the assembled
agent-specific content and the shared MRP protocol rules in the correct order,
separated by a Markdown horizontal rule.

This test imports only the ``ILlmClient`` outbound port and the test harness (no
internal core services/models) per the Acceptance-layer boundary.
"""

from pathlib import Path

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from tests.suites.acceptance.helpers import mock_response, setup_project
from teddy_executor.core.ports.outbound import ILlmClient


def test_session_system_prompt_assembles_agent_content_and_mrp(
    tmp_path: Path, monkeypatch
):
    """Scenario: The assembled system prompt delivered to the LLM starts with the
    agent-specific content, then a ``---`` separator, then the shared Markdown MRP
    protocol rules."""
    # Arrange: real workspace (anchors a real filesystem) + seeded agent prompt.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)

    # Act: drive a full session against the fake LLM.
    result = adapter.run_cli_command(["start", "-y", "-m", "instructions"])
    assert result.exit_code == 0

    # The system prompt is the first message handed to the LLM.
    system_content = llm.get_completion.call_args[1]["messages"][0]["content"]

    # Assert: the agent-specific content comes first.
    assert system_content.startswith("<prompt>Pathfinder</prompt>")

    # Assert: a Markdown horizontal rule separates the agent content from MRP.
    assert "\n\n---\n\n" in system_content

    # Assert: the shared Markdown MRP protocol rules are appended...
    assert "## Response Format" in system_content
    assert "State Transition Protocol" in system_content

    # Assert: the naming rule forbids incident numbers in test names.
    assert "Never embed incident, ticket, or bug numbers" in system_content

    # ...AFTER the agent-specific content.
    assert system_content.index("<prompt>Pathfinder</prompt>") < system_content.index(
        "State Transition Protocol"
    )
