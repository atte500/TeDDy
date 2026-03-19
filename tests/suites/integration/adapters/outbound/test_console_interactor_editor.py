from tests.harness.setup.test_environment import TestEnvironment
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment


def test_enhanced_prompt_marker_in_editor(monkeypatch, tmp_path):
    """
    Scenario 3: Enhanced PROMPT Interactive Flow
    Given a PROMPT action is executed in interactive mode
    When the user selects 'e' to open the editor
    Then the marker instruction in the temporary file must be wrapped in an HTML comment.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Prompt Test")
        .add_prompt("Please provide feedback.")
        .build()
    )

    # Configure the mocked environment from the container
    mock_env = env.get_service(ISystemEnvironment)
    temp_file = tmp_path / "prompt_edit.md"
    mock_env.create_temp_file.return_value = str(temp_file)
    mock_env.get_env.return_value = "nano"
    mock_env.which.return_value = "/usr/bin/nano"

    # Run command and simulate 'e' (editor), then Enter (confirm editor)
    cli.run_execute_with_plan(plan, input="e\n\n", interactive=True)

    # Check that run_command was called
    assert mock_env.run_command.called

    with open(temp_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Requirement: wrapped in HTML comment
    assert "<!--" in content, f"HTML comment start missing in content: {content}"
    assert "-->" in content, "HTML comment end missing"
    assert "Please enter your response above this line" in content


def test_enhanced_prompt_terminal_quick_reply_after_editor_launch(
    monkeypatch, tmp_path
):
    """
    Scenario 3: Enhanced PROMPT Interactive Flow
    And the terminal must continue to allow a single-line reply even while the editor is open.
    """
    env = TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = MarkdownPlanBuilder("Prompt Test").add_prompt("Feedback?").build()

    # Configure mock env
    mock_env = env.get_service(ISystemEnvironment)
    mock_env.create_temp_file.return_value = str(tmp_path / "quick_reply.md")
    mock_env.get_env.return_value = "nano"
    mock_env.which.return_value = "/usr/bin/nano"

    # Input: 'e' to open editor, then "Terminal Reply" to override it
    result = cli.run_execute_with_plan(
        plan, input="e\nTerminal Reply\n", interactive=True
    )

    assert result.exit_code == 0
    assert "Terminal Reply" in result.stdout


def test_enhanced_prompt_empty_response_confirmation_ux(monkeypatch, tmp_path):
    """
    User Request: Simplify empty response confirmation.
    Given a PROMPT action
    When the user presses Enter without typing anything
    Then the system should prompt to "Press [Enter] again to confirm"
    """
    TestEnvironment(monkeypatch, tmp_path).setup().with_real_interactor()
    cli = CliTestAdapter(monkeypatch, tmp_path)

    plan = MarkdownPlanBuilder("Prompt Test").add_prompt("Empty?").build()

    # Input: Enter (empty), then Enter again (confirm)
    result = cli.run_execute_with_plan(plan, input="\n\n", interactive=True)

    assert result.exit_code == 0
    assert "Press [Enter] again to confirm" in result.stderr
    # The block is omitted when empty to keep the report clean
    assert "User Response" not in result.stdout
