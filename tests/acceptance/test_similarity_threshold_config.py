import yaml
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_respects_global_similarity_threshold(tmp_path, monkeypatch):
    """
    Given a configuration file .teddy/config.yaml with similarity_threshold: 0.8
    When an EDIT action with a match score of 0.9 is executed
    Then it should pass validation (even if below the default 0.95).
    """
    # Setup workspace
    monkeypatch.chdir(tmp_path)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()

    config = {"similarity_threshold": 0.8}
    with open(teddy_dir / "config.yaml", "w") as f:
        yaml.dump(config, f)

    target_file = tmp_path / "src" / "foo.py"
    target_file.parent.mkdir()
    # Content: "def hello():\n    return 'world'"
    target_file.write_text("def hello():\n    return 'world'\n")

    # Create turn.context
    with open(tmp_path / "turn.context", "w") as f:
        f.write("src/foo.py\n")

    # A FIND block that is a ~0.85 match
    # Original: "def hello():\n    return 'world'\n"
    # Find: "def greet():\n    return 'hi world'"
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```text
### 1. Synthesis
Testing global threshold.

### 2. Justification
Justification.

### 3. Expected Outcome
Expected.

### 4. State Dashboard
State.
```

## Action Plan

### `EDIT`
- **File Path:** [src/foo.py](/src/foo.py)
- **Description:** Edit foo.py

#### `FIND:`
```python
def greet():
    return 'hi world'
```
#### `REPLACE:`
```python
def hello():
    return 'universe'
```
"""

    # We expect this to PASS because score > 0.8
    result = runner.invoke(app, ["execute", "-y", "--plan-content", plan_content])

    # If it fails validation, it would trigger the re-plan loop or show error.
    # We check if the execution was successful.
    assert "Overall Status:** SUCCESS" in result.stdout
    # Assert specific markers from the action log
    assert "EDIT" in result.stdout
    assert "foo.py" in result.stdout
    assert "Similarity Score:** 0.82" in result.stdout


def test_fallback_to_default_threshold(tmp_path, monkeypatch):
    """
    Given no similarity_threshold in config.yaml
    When an EDIT action with a match score of 0.9 is executed
    Then it should fail validation because it is below the default 0.95.
    """
    monkeypatch.chdir(tmp_path)
    teddy_dir = tmp_path / ".teddy"
    teddy_dir.mkdir()
    # Empty config
    with open(teddy_dir / "config.yaml", "w") as f:
        yaml.dump({}, f)

    target_file = tmp_path / "src" / "foo.py"
    target_file.parent.mkdir()
    target_file.write_text("def hello():\n    return 'world'\n")

    with open(tmp_path / "turn.context", "w") as f:
        f.write("src/foo.py\n")

    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```text
### 1. Synthesis
Testing default fallback.

### 2. Justification
Justification.

### 3. Expected Outcome
Expected.

### 4. State Dashboard
State.
```

## Action Plan

### `EDIT`
- **File Path:** [src/foo.py](/src/foo.py)
- **Description:** Edit foo.py

#### `FIND:`
```python
def greet():
    return 'hi world'
```
#### `REPLACE:`
```python
def hello():
    return 'universe'
```
"""

    # We expect this to FAIL because score < 0.95
    # Since it's an acceptance test, the 'execute' command will detect validation error
    result = runner.invoke(app, ["execute", "-y", "--plan-content", plan_content])

    assert "Validation Failed" in result.stdout
    assert "Similarity Score" in result.stdout
    assert "Similarity Threshold:** 0.95" in result.stdout
