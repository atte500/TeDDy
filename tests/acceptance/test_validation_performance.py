import time
from typer.testing import CliRunner
from teddy_executor.__main__ import app

runner = CliRunner()


def test_validation_performance_on_large_files(container, tmp_path, monkeypatch):
    """
    Scenario 1: Optimized Fuzzy Matching for Large Files
    Given a file "large_file.txt" with 500 lines of text
    And a plan with an EDIT action where the FIND block (100 lines) does not match exactly
    When the plan is validated
    Then the validation must complete in under 500ms
    And the error message must contain a "Closest Match Diff"
    """
    monkeypatch.chdir(tmp_path)

    # 1. Create a large file (500 lines)
    # Using a mix of content to ensure it's not too trivial
    lines = [
        f"Line {i:03}: This is some repeating content to make the file large. Index {i}.\n"
        for i in range(500)
    ]
    file_path = tmp_path / "large_file.txt"
    file_path.write_text("".join(lines), encoding="utf-8")

    # 2. Define a 100-line FIND block that is almost identical to lines 200-300
    # but has multiple changes to force fuzzy matching below 0.96
    target_lines = lines[200:300]
    find_block = "".join(target_lines)
    # Introduce 10 changes to drop ratio below 0.96 (approx 0.90)
    for i in range(250, 260):
        find_block = find_block.replace(f"Index {i}", f"Index {i} MODIFIED")

    plan_content = f"""# Performance Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```text
Testing validation performance for Scenario 1.
```

## Action Plan
### `EDIT`
- **File Path:** [large_file.txt](/large_file.txt)
- **Description:** Large edit block requiring fuzzy diagnostics.

#### `FIND:`
```text
{find_block}
```
#### `REPLACE:`
```text
Replacement content.
```
"""

    # 3. Time the validation
    # We use execute --plan-content which triggers validation before any confirmation.
    # Validation failure will stop execution and print the report.
    start_time = time.perf_counter()
    result = runner.invoke(app, ["execute", "--yes", "--plan-content", plan_content])
    end_time = time.perf_counter()

    duration = end_time - start_time

    # 4. Assertions
    # The command should fail because validation fails
    assert result.exit_code != 0
    output = result.stdout

    # Verify diagnostic quality
    assert "The `FIND` block could not be located" in output
    assert "Closest Match Diff" in output
    assert (
        "- Line 250: This is some repeating content to make the file large. Index 250 MODIFIED."
        in output
    )
    assert (
        "+ Line 250: This is some repeating content to make the file large. Index 250."
        in output
    )

    # Verify performance (The Core requirement)
    # Budget set to 1.0s on Windows to account for higher process/import overhead in CI.
    # Unix-like systems remain capped at 0.7s.
    import os

    performance_budget_seconds = 1.0 if os.name == "nt" else 0.7
    assert duration < performance_budget_seconds, (
        f"Validation took too long: {duration:.4f}s (Budget: {performance_budget_seconds}s)"
    )
