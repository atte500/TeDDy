"""Acceptance: an over-budget request fails loudly instead of stalling.

Case file 07 Preventative Measure 2 (Jidoka). The planning service computed the
request token count and the model context window but only displayed them. This
test drives the real session boundary with an over-budget LLM double and asserts
a visible error and a non-zero exit code.
"""

from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter


def _setup_minimal_project(tmp_path) -> None:
    """Create the minimal project files the start path requires."""
    prompt_dir = tmp_path / ".teddy" / "prompts"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "pathfinder.xml").write_text(
        "<prompt>Pathfinder Instructions</prompt>", encoding="utf-8"
    )
    (tmp_path / ".teddy" / "init.context").write_text("README.md", encoding="utf-8")
    (tmp_path / "README.md").write_text("Context file content", encoding="utf-8")


def test_over_budget_request_surfaces_visible_error(tmp_path, monkeypatch):
    """Scenario: an over-budget request fails loudly instead of stalling."""
    from teddy_executor.core.ports.outbound import ILlmClient

    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    _setup_minimal_project(tmp_path)

    mock_llm_client = env.get_service(ILlmClient)
    mock_llm_client.get_token_count.return_value = 200_000
    mock_llm_client.get_context_window.return_value = 128_000

    result = adapter.run_start(
        ["--agent", "pathfinder", "-y", "-m", "oversized request"]
    )

    combined = result.stdout + (result.stderr or "")
    assert result.exit_code != 0, combined
    assert "Context Window Exceeded" in combined
    assert "200000" in combined
    assert "128000" in combined
    mock_llm_client.get_completion.assert_not_called()
