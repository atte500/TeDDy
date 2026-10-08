"""Acceptance gate for MRP base prompt injection (MRP Base Prompt slice).

Subcutaneous end-to-end test: drive a real session through the CLI, capture the
system prompt the harness fake LLM receives, and assert it carries the assembled
agent-name header, the agent-specific content, and the shared MRP protocol rules
in the correct order.

This test imports only the ``ILlmClient`` outbound port and the test harness (no
internal core services/models) per the Acceptance-layer boundary.
"""

from pathlib import Path

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from tests.suites.acceptance.helpers import mock_response, setup_project
from teddy_executor.core.ports.outbound import ILlmClient


def test_session_system_prompt_assembles_header_agent_content_and_mrp(
    tmp_path: Path, monkeypatch
):
    """Scenario: The assembled system prompt delivered to the LLM starts with the
    agent-name header, contains the agent-specific XML, and appends the shared MRP
    protocol rules after it."""
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

    # Assert: agent-name header derived from the XML filename, capitalized.
    assert system_content.startswith("Agent Name: Pathfinder")

    # Assert: the agent-specific content is present.
    assert "<prompt>Pathfinder</prompt>" in system_content

    # Assert: the shared MRP protocol rules are appended...
    assert "<response_format>" in system_content
    assert "State Transition Protocol" in system_content

    # ...AFTER the agent-specific content.
    assert system_content.index("<prompt>Pathfinder</prompt>") < system_content.index(
        "<response_format>"
    )
