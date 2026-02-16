from pathlib import Path
from unittest.mock import MagicMock, patch
from typer.testing import CliRunner

from teddy_executor.main import app, create_container
from teddy_executor.core.ports.outbound import IUserInteractor
from .helpers import parse_markdown_report
from .plan_builder import MarkdownPlanBuilder


def test_interactive_approval_and_execution(tmp_path: Path, monkeypatch):
    """
    Given a plan from the clipboard,
    When the user runs `execute` interactively and approves,
    Then the action should be executed successfully.
    """
    # Arrange
    runner = CliRunner()
    test_file = tmp_path / "test_file.txt"
    file_content = "Interactive Hello"

    builder = MarkdownPlanBuilder("Test Interactive Approval")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{test_file.name}](/{test_file.name})",
            "Description": "Create a file interactively.",
        },
        content_blocks={"": ("text", file_content)},
    )
    plan_content = builder.build()

    # Mock the UserInteractor to simulate user approval
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        with patch("teddy_executor.main.container", test_container):
            result = runner.invoke(
                app, ["execute", "--no-copy", "--plan-content", plan_content]
            )  # No --yes flag for interactive

    # Assert
    assert result.exit_code == 0
    assert test_file.exists()
    assert test_file.read_text() == file_content
    mock_interactor.confirm_action.assert_called_once()

    report = parse_markdown_report(result.stdout)
    assert report["run_summary"]["Overall Status"] == "SUCCESS"


def test_interactive_skip_with_reason(tmp_path: Path, monkeypatch):
    """
    Given a plan from the clipboard,
    When the user runs `execute` interactively and denies with a reason,
    Then the action should be skipped and the reason reported.
    """
    # Arrange
    runner = CliRunner()
    test_file = tmp_path / "test.txt"

    builder = MarkdownPlanBuilder("Test Interactive Skip")
    builder.add_action(
        "CREATE",
        params={
            "File Path": f"[{test_file.name}](/{test_file.name})",
            "Description": "A file that will be skipped.",
        },
        content_blocks={"": ("text", "This should not be created.")},
    )
    plan_content = builder.build()

    # Mock the UserInteractor to simulate user denial with a reason
    mock_interactor = MagicMock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (False, "Manual check needed")

    test_container = create_container()
    test_container.register(IUserInteractor, instance=mock_interactor)

    # Act
    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        with patch("teddy_executor.main.container", test_container):
            # We must provide some input to stdin to satisfy the `input()`
            # call inside the mocked `confirm_action` if it were real.
            # Even with a mock, Typer's runner may expect it.
            result = runner.invoke(
                app,
                ["execute", "--no-copy", "--plan-content", plan_content],
                input="""n
Manual check needed
""",
            )

    # Assert
    # A skipped plan is not a system failure, so the exit code should be 0.
    assert result.exit_code == 0
    assert not test_file.exists()

    report = parse_markdown_report(result.stdout)
    # The run is a SUCCESS because the system correctly handled the user's choice.
    assert report["run_summary"]["Overall Status"] == "SUCCESS"
    action_log = report["action_logs"][0]
    assert action_log["status"] == "SKIPPED"
    expected_details = "User skipped this action. Reason: Manual check needed"
    assert expected_details in action_log["details"]["error"]
