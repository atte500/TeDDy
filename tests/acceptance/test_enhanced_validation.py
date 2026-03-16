from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_structural_validation_error_format(container, tmp_path, monkeypatch):
    """
    Scenario 1: Structural Validation Error
    Given a plan with top-level structural errors (missing ## Rationale)
    When the plan is executed
    Then it should fail with a rich diagnostic report.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").touch()
    plan_content = """# Plan Missing Rationale
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Action Plan
### `READ`
- **Resource:** [README.md](/README.md)
"""

    result = runner.invoke(app, ["execute", "--plan-content", plan_content])

    assert result.exit_code != 0
    output = result.stdout

    # Assertions for the new rich format
    assert '[✓] [000] Heading (Level 1): "Plan Missing Rationale"' in output
    assert '[✓] [001] List: "Status: Green 🟢' in output
    assert (
        "[✗] [002] Heading (Level 2): \"Action Plan\" (Error: Expected a Level 2 Heading containing 'Rationale')"
        in output
    )

    # Verify the general headers are still present or updated appropriately
    assert "### Actual Document Structure" in output


def test_logical_validation_error_format(container, tmp_path, monkeypatch):
    """
    Scenario 2: Logical Validation Error (Missing File)
    Given an EDIT action on a non-existent file
    Then the action heading itself must be marked [✗].
    """
    monkeypatch.chdir(tmp_path)
    plan_content = """# Plan with Missing File
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
```text
Rationale content.
```

## Action Plan
### `EDIT`
- **File Path:** [non_existent_file.py](/non_existent_file.py)
- **Description:** Missing file.

#### `FIND:`
```python
print("Hello")
```
#### `REPLACE:`
```python
print("Goodbye")
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "File to edit does not exist: non_existent_file.py" in output
    # When file is missing, the heading is the failure point
    assert (
        '[✗] [005] Heading (Level 3): "EDIT" (Error: File to edit does not exist: non_existent_file.py)'
        in output
    )


def test_surgical_code_block_highlighting(container, tmp_path, monkeypatch):
    """
    Scenario 3: Surgical Code Block Highlighting
    Given an EDIT action on an existing file but with a non-matching FIND block
    Then the action heading must be [✓]
    And the specific FIND Code Block must be [✗].
    """
    # Isolate from the real repo
    (tmp_path / "README.md").write_text("# Test README", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    plan_content = """# Plan with Mismatched Find
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Pathfinder

## Rationale
```text
Rationale content.
```

## Action Plan
### `EDIT`
- **File Path:** [README.md](/README.md)
- **Description:** Matching file, non-matching content.

#### `FIND:`
```text
THIS CONTENT DEFINITELY DOES NOT EXIST IN README
```
#### `REPLACE:`
```text
NEW CONTENT
```
"""
    result = runner.invoke(app, ["execute", "--plan-content", plan_content])
    output = result.stdout

    assert "## Validation Errors:" in output
    assert "The `FIND` block could not be located" in output

    # AST Visualization
    assert "### Plan AST with Highlighted Failures" in output
    # Heading is valid (file exists and in context)
    assert '[✓] [005] Heading (Level 3): "EDIT"' in output
    # Metadata list is valid
    assert '  [✓] [006] List: "File Path: README.md' in output
    # Surgical Failure: The specific FIND Code Block
    assert (
        '[✗] [008] Code Block (3 backticks): "THIS CONTENT DEFINITELY DOES NOT EXIST IN README"'
        in output
    )
    assert (
        "(Error: The `FIND` block could not be located in the file: README.md)"
        in output
    )
