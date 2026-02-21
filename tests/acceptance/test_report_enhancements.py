from typer.testing import CliRunner
from teddy_executor.main import app


def test_smart_fencing_for_validation_errors(tmp_path, monkeypatch):
    runner = CliRunner()
    monkeypatch.chdir(tmp_path)

    # Setup a target file for an EDIT action
    target_file = tmp_path / "target.py"
    target_file.write_text("def hello():\n    pass\n", encoding="utf-8")

    # Create a plan with a FIND block that will fail validation (does not match file)
    # The FIND block contains a nested code block, simulating the need for smart fencing.
    plan_content = """# Test Plan
## Action Plan
### `EDIT`
- **File Path:** target.py
- **Description:** Attempt to edit a file with a failing, backtick-heavy FIND block.

#### `FIND:`
```python
def old_hello():
    ```nested```
```
#### `REPLACE:`
```python
def new_hello():
    pass
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    # Assert validation failed
    assert result.exit_code != 0
    assert "Validation Failed" in result.stdout

    # Assert the FIND block is present in the output
    assert "```nested```" in result.stdout

    # Assert smart fencing was applied. Since the inner content has 3 backticks,
    # the fence MUST use at least 4 backticks.
    assert "````\ndef old_hello():" in result.stdout


def test_chat_with_user_report_omits_prompt(monkeypatch):
    runner = CliRunner()

    plan_content = """# Test Plan
## Action Plan
### `CHAT_WITH_USER`
The AI prompt string here.
"""
    # Mock user input for the chat action and answer 'yes' to the approval prompt.
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content],
        input="y\nUser response string here.\n",
    )

    assert result.exit_code == 0
    assert "User response string here." in result.stdout
    assert "The AI prompt string here." not in result.stdout


def test_invoke_report_omits_details(monkeypatch):
    runner = CliRunner()

    plan_content = """# Test Plan
## Action Plan
### `INVOKE`
- **Agent:** PathFinder

Hello PathFinder!
"""
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="y\n"
    )

    assert result.exit_code == 0
    assert "- **Details:**" not in result.stdout
