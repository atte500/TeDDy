from typer.testing import CliRunner
from teddy_executor.__main__ import app


def test_prompt_report_omits_prompt(monkeypatch):
    runner = CliRunner()

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `PROMPT`
The AI prompt string here.
"""
    # Mock user input for the chat action. Note: PROMPT auto-approves.
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content],
        input="User response string here.\n",
    )

    assert result.exit_code == 0
    assert "User response string here." in result.stdout
    assert "The AI prompt string here." not in result.stdout


def test_invoke_report_omits_details(monkeypatch):
    runner = CliRunner()

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `INVOKE`
- **Agent:** PathFinder

Hello PathFinder!
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content], input="\n")

    assert result.exit_code == 0
    assert "- **Details:**" not in result.stdout


def test_dynamic_language_in_code_blocks(tmp_path, monkeypatch):
    """
    Ensures the system executes multiple READ actions correctly.
    Formatting details are covered in unit tests.
    """
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Setup files
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    py_file = src_dir / "main.py"
    py_file.write_text("print('hello')", encoding="utf-8")

    cfg_file = tmp_path / "config.cfg"
    cfg_file.write_text("debug=true", encoding="utf-8")

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

## Action Plan
### `READ`
- **Resource:** src/main.py

### `READ`
- **Resource:** config.cfg
"""
    result = runner.invoke(app, ["execute", "-y", "--plan-content", plan_content])

    assert result.exit_code == 0
    # High-level check that resources were read
    assert "Resource Contents" in result.stdout
    assert "print('hello')" in result.stdout
    assert "debug=true" in result.stdout
