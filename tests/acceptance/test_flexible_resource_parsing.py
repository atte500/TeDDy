from typer.testing import CliRunner
from teddy_executor.__main__ import app
from pathlib import Path
import uuid

runner = CliRunner()


def test_read_action_supports_file_path_alias():
    # Given a file exists in the current project root (safe for validation)
    test_file_path = f"test_read_alias_{uuid.uuid4().hex}.txt"
    test_file = Path(test_file_path)
    test_file.write_text("hello world", encoding="utf-8")

    try:
        # And a plan with a READ action using the 'File Path' alias
        plan_content = f"""# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```
Testing alias.
```

## Action Plan
### `READ`
- **File Path:** [{test_file_path}](/{test_file_path})
- **Description:** Read the test file.
"""

        # When the plan is executed
        # We use --no-copy to avoid clipboard issues in tests
        result = runner.invoke(
            app, ["execute", "--plan-content", plan_content, "--no-copy"], input="y\n"
        )

        # Then it should succeed and the report should contain the file content
        assert result.exit_code == 0, f"Execution failed: {result.stdout}"
        assert "hello world" in result.stdout
    finally:
        if test_file.exists():
            test_file.unlink()


def test_read_action_fails_when_url_provided_in_file_path_alias():
    # Given a plan with a READ action using 'File Path' with a URL
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```
Testing URL constraint.
```

## Action Plan
### `READ`
- **File Path:** [www.google.com](https://www.google.com)
- **Description:** Try to read a URL as a file path.
"""

    # When the plan is executed
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content, "--no-copy"]
    )

    # Then validation should fail with a "Strict Local Only" error
    assert result.exit_code != 0, f"Execution should have failed: {result.stdout}"
    assert "Strict Local Only" in result.stdout, (
        f"Error message missing: {result.stdout}"
    )


def test_prune_action_supports_file_path_alias():
    # Given a plan with a PRUNE action using the 'File Path' alias
    # Note: We use a file that actually exists in the context (README.md) to pass validation
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```
Testing PRUNE alias.
```

## Action Plan
### `PRUNE`
- **File Path:** [README.md](/README.md)
- **Description:** Prune the README.
"""

    # When the plan is executed (manually providing context-mocked path)
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content, "--no-copy"], input="n\n"
    )

    # Then it should parse and find the action even if execution is skipped/ignored
    assert "### `PRUNE`: [README.md](/README.md)" in result.stdout


def test_prune_action_fails_when_url_provided_in_file_path_alias():
    # Given a plan with a PRUNE action using 'File Path' with a URL
    plan_content = """# Test Plan
- **Status:** Green 🟢
- **Plan Type:** Implementation
- **Agent:** Developer

## Rationale
```
Testing PRUNE URL constraint.
```

## Action Plan
### `PRUNE`
- **File Path:** [www.google.com](https://www.google.com)
- **Description:** Try to prune a URL.
"""

    # When the plan is executed
    result = runner.invoke(
        app, ["execute", "--plan-content", plan_content, "--no-copy"]
    )

    # Then validation should fail with a "Strict Local Only" error
    assert result.exit_code != 0
    assert "Strict Local Only" in result.stdout
