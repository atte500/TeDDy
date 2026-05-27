from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.observers.report_parser import ReportParser


def test_message_turn_skips_approval(env: TestEnvironment, monkeypatch):
    """
    Given a parsed plan containing only a "MESSAGE" action
    When the orchestrator executes the plan
    Then the user is NOT prompted for approval (Skip Approval Gate)
    And the execution report confirms the message was delivered
    """
    # Arrange
    assert env.workspace is not None
    cli = CliTestAdapter(monkeypatch, env.workspace)
    interactor = env.get_mock_user_interactor()

    plan_content = (
        MarkdownPlanBuilder("Communication Turn").with_message("Hello World!").build()
    )

    # Act
    result = cli.run_execute_with_plan(plan_content=plan_content, interactive=True)

    # Assert
    assert result.exit_code == 0
    report = ReportParser(result.stdout)
    assert report.run_summary["Overall Status"] == "SUCCESS"
    assert any(log.type == "MESSAGE" for log in report.action_logs)

    # Verify no confirmation prompt was shown for the MESSAGE action
    confirm_calls = [
        c
        for c in interactor.confirm_action.call_args_list
        if c.kwargs.get("action") and c.kwargs["action"].type == "MESSAGE"
    ]
    assert len(confirm_calls) == 0, (
        "MESSAGE action should have skipped the confirmation prompt."
    )


def test_legacy_actions_trigger_terminal_warnings(env: TestEnvironment, monkeypatch):
    """
    Given a plan containing "PROMPT"
    When the plan is executed
    Then a deprecation warning is displayed in the terminal
    And the final execution report does NOT contain these warnings
    """
    # Arrange
    assert env.workspace is not None
    cli = CliTestAdapter(monkeypatch, env.workspace)
    interactor = env.get_mock_user_interactor()

    plan_content = (
        MarkdownPlanBuilder("Legacy Turn").add_prompt("Hello Legacy!").build()
    )

    # Act
    # We need to provide 'y' for the prompt if it still triggers one
    interactor.confirm_action.return_value = (True, "")
    result = cli.run_execute_with_plan(plan_content=plan_content, interactive=True)

    # Assert
    assert result.exit_code == 0

    # Check if notify_warning was called with the deprecation message
    warning_calls = [
        c
        for c in interactor.notify_warning.call_args_list
        if "deprecated" in c.args[0] and "PROMPT" in c.args[0]
    ]
    assert len(warning_calls) > 0, (
        "Deprecation warning for PROMPT should have been displayed."
    )

    # Ensure warning is NOT in the report (stdout)
    assert "deprecated" not in result.stdout.lower()
