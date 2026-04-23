from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.services.execution_orchestrator import ExecutionOrchestrator


def _setup_mock_reviewer(monkeypatch, tmp_path):
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup().with_real_interactor()

    # Mock the PlanReviewer
    mock_reviewer = env.mock_port(IPlanReviewer)
    mock_reviewer.review.side_effect = lambda p: p
    mock_reviewer.review_action.return_value = (True, "")

    # Force injection by monkeypatching the class constructor.
    # This ensures every instance of ExecutionOrchestrator gets the mock reviewer.
    original_init = ExecutionOrchestrator.__init__

    def mock_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._plan_reviewer = mock_reviewer

    monkeypatch.setattr(ExecutionOrchestrator, "__init__", mock_init)
    return mock_reviewer


def test_single_prompt_action_bypasses_tui_review(tmp_path, monkeypatch):
    """
    Scenario: Single PROMPT actions should execute immediately without TUI approval.
    """
    mock_reviewer = _setup_mock_reviewer(monkeypatch, tmp_path)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan_content = (
        MarkdownPlanBuilder("Single Prompt Plan").add_prompt("Hello User").build()
    )

    # Bypass the reviewer, goes straight to interactor's prompt for the PROMPT response.
    user_response = "Confirmed"
    cli_input = f"{user_response}\n"

    adapter.run_cli_command(
        ["execute", "--no-copy", "--plan-content", plan_content], input=cli_input
    )

    # ASSERTIONS: Both bulk and sequential review should be bypassed
    assert not mock_reviewer.review.called, (
        "Bulk Reviewer should have been bypassed for single PROMPT action"
    )
    assert not mock_reviewer.review_action.called, (
        "Sequential Reviewer should have been bypassed for single PROMPT action"
    )


def test_multiple_actions_still_require_review(tmp_path, monkeypatch):
    """
    Scenario: Plans with multiple actions still require TUI approval.
    """
    mock_reviewer = _setup_mock_reviewer(monkeypatch, tmp_path)
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    # Use EXECUTE actions to avoid validation failures (READ requires existing files)
    plan_content = (
        MarkdownPlanBuilder("Multi-Action Plan")
        .add_execute("echo Hello", description="Action 1")
        .add_execute("echo World", description="Action 2")
        .build()
    )

    # Input for reviewer (2 actions)
    # 1. EXECUTE 1: \n (accept)
    # 2. EXECUTE 2: \n (accept)
    cli_input = "\n\n"

    adapter.run_cli_command(
        ["execute", "--no-copy", "--plan-content", plan_content], input=cli_input
    )

    # ASSERTIONS: Both bulk and sequential review should be called
    assert mock_reviewer.review.called, (
        "Bulk Reviewer should have been called for multi-action plan"
    )
    assert mock_reviewer.review_action.called, (
        "Sequential Reviewer should have been called for multi-action plan"
    )
