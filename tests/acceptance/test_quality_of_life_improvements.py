from pathlib import Path
from tests.drivers.plan_builder import MarkdownPlanBuilder
from tests.drivers.cli_adapter import CliTestAdapter
from tests.setup.test_environment import TestEnvironment
from teddy_executor.core.ports.outbound import IUserInteractor


def test_interactive_prompt_shows_description(tmp_path: Path, monkeypatch):
    """Scenario: Interactive confirmation prompt includes action description."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    interactor = env.get_service(IUserInteractor)  # type: ignore[type-abstract]

    plan = (
        MarkdownPlanBuilder("QoL: Description")
        .add_create("test.txt", "hello", description="Special description")
        .build()
    )

    interactor.confirm_action.return_value = (True, "")  # type: ignore[attr-defined]

    adapter.execute_plan(plan, interactive=True, user_input="y\n")

    interactor.confirm_action.assert_called_once()  # type: ignore[attr-defined]
    _, kwargs = interactor.confirm_action.call_args  # type: ignore[attr-defined]
    assert "Special description" in kwargs["action_prompt"]


def test_prompt_action_skips_approval_prompt(tmp_path: Path, monkeypatch):
    """Scenario: PROMPT action skips the y/n approval prompt in interactive mode."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)
    interactor = env.get_service(IUserInteractor)  # type: ignore[type-abstract]

    plan = MarkdownPlanBuilder("QoL: Skip Prompt Approval").add_prompt("Hello?").build()

    interactor.ask_question.return_value = "World"  # type: ignore[attr-defined]

    adapter.execute_plan(plan, interactive=True, user_input="\n")

    # PROMPT should not trigger y/n confirmation
    interactor.confirm_action.assert_not_called()  # type: ignore[attr-defined]
    interactor.ask_question.assert_called_once()  # type: ignore[attr-defined]


def test_read_action_report_formats_multiline_content(tmp_path: Path, monkeypatch):
    """Scenario: READ action report correctly preserves multiline file content."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    content = "line one\nline two"
    (tmp_path / "multi.txt").write_text(content, encoding="utf-8")

    plan = MarkdownPlanBuilder("QoL: Read Multiline").add_read("multi.txt").build()

    report = adapter.execute_plan(plan)

    assert report.action_was_successful(0)
    assert "line one" in report.stdout
    assert "line two" in report.stdout


def test_read_action_preserves_markdown_formatting(tmp_path: Path, monkeypatch):
    """Scenario: READ action report preserves complex markdown content."""
    env = TestEnvironment(monkeypatch, tmp_path)
    env.setup()
    adapter = CliTestAdapter(monkeypatch, tmp_path)

    content = "# Header\n\n```python\nprint('hi')\n```"
    (tmp_path / "complex.md").write_text(content, encoding="utf-8")

    plan = MarkdownPlanBuilder("QoL: Read Markdown").add_read("complex.md").build()

    report = adapter.execute_plan(plan)

    assert report.action_was_successful(0)
    assert "# Header" in report.stdout
    assert "print('hi')" in report.stdout
