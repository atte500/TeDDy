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
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

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
- **Status:** Green 🟢
- **Agent:** Developer

## Rationale
````text
Rationale.
````

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
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content], input="y\n"
    )

    assert result.exit_code == 0
    assert "- **Details:**" not in result.stdout


def test_dynamic_language_in_code_blocks(tmp_path, monkeypatch):
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

    # Check for python code block
    assert "```python\nprint('hello')\n```" in result.stdout
    # Check for mapped config block (cfg -> ini)
    assert "```ini\ndebug=true\n```" in result.stdout
