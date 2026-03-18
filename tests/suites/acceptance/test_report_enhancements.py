from pathlib import Path
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.drivers.cli_adapter import CliTestAdapter
from tests.harness.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import IUserInteractor


def test_prompt_report_omits_prompt(tmp_path: Path, monkeypatch):
    """Scenario: PROMPT report includes user response but excludes the AI's prompt string."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    interactor = env.get_service(IUserInteractor)  # type: ignore[type-abstract]

    prompt_text = "The AI prompt string here."
    user_response = "User response string here."
    interactor.ask_question.return_value = user_response  # type: ignore[attr-defined]

    plan = MarkdownPlanBuilder("Prompt Test").add_prompt(prompt_text).build()

    # PROMPT triggers interactor.ask_question
    report = adapter.execute_plan(plan, interactive=True)

    assert report.action_was_successful(0)
    assert user_response in report.stdout
    assert prompt_text not in report.stdout


def test_invoke_report_omits_details(tmp_path: Path, monkeypatch):
    """Scenario: INVOKE report omits the 'Details' section for control-flow actions."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    plan = (
        MarkdownPlanBuilder("Invoke Test")
        .add_invoke("PathFinder", "Hello PathFinder!")
        .build()
    )

    # Interactive mode triggers manual handoff confirmation (mocked to True)
    report = adapter.execute_plan(plan, interactive=True, user_input="\n")

    assert report.action_was_successful(0)
    assert "- **Details:**" not in report.stdout


def test_dynamic_language_in_code_blocks(tmp_path: Path, monkeypatch):
    """Scenario: Multiple READ actions are correctly formatted in the report."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    (tmp_path / "main.py").write_text("print('hello')", encoding="utf-8")
    (tmp_path / "config.cfg").write_text("debug=true", encoding="utf-8")

    plan = (
        MarkdownPlanBuilder("Read Test")
        .add_read("main.py")
        .add_read("config.cfg")
        .build()
    )

    report = adapter.execute_plan(plan)

    assert report.action_was_successful(0)
    assert report.action_was_successful(1)
    assert "Resource Contents" in report.stdout
    assert "print('hello')" in report.stdout
    assert "debug=true" in report.stdout
