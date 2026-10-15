"""Acceptance gate for the pipeline-mode default agent.

Subcutaneous end-to-end test: drive real sessions through the CLI in pipeline and
non-pipeline mode, capture the system prompt the harness fake LLM receives, and
assert the resolved agent is Assistant for pipeline runs and Pathfinder otherwise.

This test imports only the ``ILlmClient`` outbound port and the test harness (no
internal core services/models) per the Acceptance-layer boundary.
"""

from pathlib import Path

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from tests.suites.acceptance.helpers import mock_response, setup_project
from teddy_executor.core.ports.outbound import ILlmClient


def _seed_agent_prompt(tmp_path: Path, agent: str) -> None:
    """Seed an overridable agent prompt in ``.teddy/prompts/`` (deterministic)."""
    prompts = tmp_path / ".teddy" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / f"{agent}.xml").write_text(
        f"<prompt>{agent.capitalize()}</prompt>", encoding="utf-8"
    )


@pytest.mark.timeout(30)
def test_pipeline_run_defaults_to_assistant_agent(tmp_path: Path, monkeypatch):
    """Scenario: a pipeline run (no explicit -a) resolves to the Assistant agent."""
    # Arrange: real workspace + seeded assistant prompt; the fake LLM returns a
    # MESSAGE-only plan so the pipeline loop terminates cleanly (no hang).
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)
    _seed_agent_prompt(tmp_path, "assistant")

    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Init").with_message("Ready.").build()
    llm.get_completion.return_value = mock_response(plan)

    # Act: drive a pipeline run against the fake LLM.
    result = adapter.run_cli_command(["start", "-p", "-m", "list the repo tree"])
    assert result.exit_code == 0

    # Assert: the pipeline run resolved the assistant agent.
    system_content = llm.get_completion.call_args[1]["messages"][0]["content"]
    assert system_content.startswith("<prompt>Assistant</prompt>")


@pytest.mark.timeout(30)
def test_non_pipeline_run_defaults_to_pathfinder_agent(tmp_path: Path, monkeypatch):
    """Scenario: a run without -p keeps the Pathfinder default."""
    # Arrange: real workspace; the fake LLM returns an EXECUTE plan.
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)

    llm = env.get_service(ILlmClient)
    plan = MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    llm.get_completion.return_value = mock_response(plan)

    # Act: drive a non-pipeline run against the fake LLM.
    result = adapter.run_cli_command(["start", "-y", "-m", "survey the backlog"])
    assert result.exit_code == 0

    # Assert: the non-pipeline run keeps the pathfinder agent.
    system_content = llm.get_completion.call_args[1]["messages"][0]["content"]
    assert system_content.startswith("<prompt>Pathfinder</prompt>")
