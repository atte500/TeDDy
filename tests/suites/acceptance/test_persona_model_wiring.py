"""Acceptance: a session started with ``-a`` flows the persona model end to end.

The persona model must reach BOTH the startup identity banner and the completion
request (as the effective model plus the persona overlay), while the global
``llm`` block still supplies the shared defaults. This is the end-to-end tracer
bullet for the wiring over a real filesystem. Precedence refinements, blank
fallback, and metadata separation are the Core and Migration deliverables.
"""

from pathlib import Path

import pytest

from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.test_environment import TestEnvironment
from tests.suites.acceptance.helpers import mock_response, setup_project
from teddy_executor.core.ports.outbound import IConfigService, ILlmClient

PERSONA_MODEL = "anthropic/claude-sonnet-4-5"
GLOBAL_MODEL = "openai/gpt-4o"


def _configure_persona_config(env) -> None:
    """Drive the config double so ``agents.architect`` and ``llm.model`` differ."""
    config = env.get_service(IConfigService)

    def _get_setting(key, default=None):
        if key == "agents":
            return {"architect": {"model": PERSONA_MODEL, "timeout": 300}}
        if key == "llm.model":
            return GLOBAL_MODEL
        if key == "llm.api_key":
            return "sk-test-key"  # pragma: allowlist secret
        if key == "editor":
            return "disabled"
        return default

    config.get_setting.side_effect = _get_setting


def _seed_architect_prompt(tmp_path: Path) -> None:
    """Seed an overridable architect prompt so preflight validation passes."""
    prompts = tmp_path / ".teddy" / "prompts"
    prompts.mkdir(parents=True, exist_ok=True)
    (prompts / "architect.xml").write_text(
        "<prompt>Architect</prompt>", encoding="utf-8"
    )


@pytest.mark.timeout(30)
def test_persona_model_reaches_banner_and_completion(tmp_path: Path, monkeypatch):
    """Scenario: ``-a architect`` selects the persona model across the turn."""
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_shell()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    setup_project(tmp_path)
    _seed_architect_prompt(tmp_path)
    _configure_persona_config(env)

    llm = env.get_service(ILlmClient)
    llm.get_completion.return_value = mock_response(
        MarkdownPlanBuilder("Init").add_execute("echo 1").build()
    )

    # Act: start a session under the architect persona, executing one turn.
    result = adapter.run_cli_command(
        ["start", "-a", "architect", "-y", "-m", "plan the auth module"]
    )

    assert result.exit_code == 0

    # The completion carries the persona model and its overlay.
    completion_kwargs = llm.get_completion.call_args[1]
    assert completion_kwargs["model"] == PERSONA_MODEL
    assert completion_kwargs["llm_overrides"] == {
        "model": PERSONA_MODEL,
        "timeout": 300,
    }

    # The startup identity banner reports the same effective model.
    combined = result.stdout + (result.stderr or "")
    assert f"Model: {PERSONA_MODEL}" in combined
