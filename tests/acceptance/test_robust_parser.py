import os

import pytest
from typer.testing import CliRunner

from teddy_executor.main import app

runner = CliRunner()


@pytest.mark.xfail(reason="Parser does not yet support ThematicBreak as a separator.")
def test_plan_with_thematic_break_separator_parses_successfully():
    """
    Given a plan with a '---' separator between actions,
    When the plan is executed,
    Then it should parse without validation errors and execute successfully.
    """
    plan_content = """
# Test Plan with Thematic Break Separator
## Action Plan
### `CREATE`
- **File Path:** [file1.txt](/file1.txt)
- **Description:** First file.
````text
content1
````
---
### `CREATE`
- **File Path:** [file2.txt](/file2.txt)
- **Description:** Second file.
````text
content2
````
"""
    result = runner.invoke(
        app,
        ["execute", "--plan-content", plan_content, "--no-copy", "--non-interactive"],
        catch_exceptions=False,
    )

    try:
        assert result.exit_code == 0
        assert "Execution Report: SUCCESS" in result.stdout
        assert "CREATE: First file." in result.stdout
        assert "CREATE: Second file." in result.stdout
        assert os.path.exists("file1.txt")
        assert os.path.exists("file2.txt")
    finally:
        # cleanup
        if os.path.exists("file1.txt"):
            os.remove("file1.txt")
        if os.path.exists("file2.txt"):
            os.remove("file2.txt")
