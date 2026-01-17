# RCA: YAML Report Formatting Bug for Complex Strings

## 1. Summary
When executing a `read` action on a file with complex content (e.g., `README.md`), the final YAML execution report incorrectly formatted the multi-line string content. Instead of using a human-readable literal block (`|`), it produced a single, long line with escaped newline characters (`\n`). This defeated the goal of having easily readable reports.

## 2. Root Cause Analysis
The root cause was a subtle, content-dependent safety feature present in both the standard `PyYAML` library and its fork, `ruamel.yaml`.

-   **Flawed Premise:** The initial assumption was that a YAML library could be configured to *always* use the literal block style for any multi-line string.
-   **Ground Truth:** YAML libraries inspect string content for characters that could be misinterpreted as special YAML syntax (e.g., `---`, `:`, `|`, lines with trailing whitespace). If such characters are found, the library intentionally ignores style hints and defaults to a "safer," single-quoted, escaped string format. This is a feature to prevent data corruption, but it caused the undesirable formatting in our reports.

The problem was not a bug in the application's logic, but a fundamental misunderstanding of the YAML serialization contract.

## 3. Verified Solution (Immediate Fix)
The solution is to replace `PyYAML` with the more powerful `ruamel.yaml` library and configure it with a custom `Representer` that explicitly overrides the default safety-checking behavior for all multi-line strings.

### Step 1: Update Dependencies
In `packages/executor/pyproject.toml`, replace `pyyaml` with `ruamel.yaml`.

**Find:**
```toml
pyyaml = "^6.0.1"
```

**Replace with:**
```toml
ruamel-yaml = "^0.18.6"
```
Then run `poetry -C packages/executor lock` and `poetry -C packages/executor install`.

### Step 2: Update the CLI Formatter
Replace the contents of `packages/executor/src/teddy_executor/adapters/inbound/cli_formatter.py` with the following verified code:

```python
import io
import json
import os
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.representer import RoundTripRepresenter

from teddy_executor.core.domain.models import ContextResult, ExecutionReport


# --- Start of Verified Fix ---

class MyRepresenter(RoundTripRepresenter):
    """Custom representer to force literal style for multi-line strings."""
    def represent_str(self, s: str):
        if '\n' in s:
            return self.represent_scalar('tag:yaml.org,2002:str', s, style='|')
        return super().represent_str(s)

# Register the custom representer to handle all strings
MyRepresenter.add_representer(str, MyRepresenter.represent_str)

# --- End of Verified Fix ---


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses, enums, etc., to JSON-serializable types."""
    if is_dataclass(obj):
        return to_dict(asdict(obj))
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_dict(i) for i in obj]
    elif isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    return obj


def format_report_as_yaml(report: ExecutionReport) -> str:
    """Formats the full execution report into a YAML string."""
    report_dict = to_dict(report)
    cleaned_action_logs = []
    if "action_logs" in report_dict:
        for log in report_dict["action_logs"]:
            if isinstance(log.get("details"), str):
                try:
                    log["details"] = json.loads(log["details"])
                except (json.JSONDecodeError, TypeError):
                    pass
            cleaned_action_logs.append(log)
        report_dict["action_logs"] = cleaned_action_logs

    # --- Start of Verified Fix ---
    yaml = YAML()
    yaml.Representer = MyRepresenter
    yaml.indent(mapping=2, sequence=4, offset=2)
    string_stream = io.StringIO()
    yaml.dump(report_dict, string_stream)
    return string_stream.getvalue()
    # --- End of Verified Fix ---


def _get_file_extension(file_path: str) -> str:
    """Extracts the file extension for code block formatting."""
    ext_map = {
        ".py": "python",
        ".md": "markdown",
        ".js": "javascript",
        ".html": "html",
        ".css": "css",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".sh": "shell",
    }
    ext = os.path.splitext(file_path)[1]
    return ext_map.get(ext, "")


def format_project_context(context: ContextResult) -> str:
    """Formats the ContextResult DTO into a structured string for display."""
    output_parts = []
    output_parts.append("# System Information")
    for key, value in sorted(context.system_info.items()):
        if key != "python_version":
            output_parts.append(f"{key}: {value}")
    output_parts.append("\n# Repository Tree")
    output_parts.append(context.repo_tree)
    output_parts.append("\n# Context Vault")
    output_parts.extend(sorted(context.context_vault_paths))
    output_parts.append("\n# File Contents")
    for path in sorted(context.file_contents.keys()):
        content = context.file_contents[path]
        if content is None:
            output_parts.append(f"--- {path} (Not Found) ---")
        else:
            extension = _get_file_extension(path)
            output_parts.append(f"--- {path} ---")
            output_parts.append(f"````{extension}\n{content}\n````")
    return "\n".join(output_parts)
```

## 4. Preventative Measures (Architectural Recommendation)
**Decision:** Standardize on `ruamel.yaml` for all YAML serialization tasks within the project.
**Rationale:** The `PyYAML` library is largely unmaintained and has known bugs (like this one) that will not be fixed. `ruamel.yaml` is a well-maintained fork with a more powerful and correct API. Adopting it as the project standard prevents this and other potential serialization bugs from recurring.

## 5. Recommended Regression Test
Add the following acceptance test to `packages/executor/tests/acceptance/test_quality_of_life_improvements.py` to ensure this specific bug does not regress.

```python
import pytest
from typer.testing import CliRunner

from teddy_executor.main import app

runner = CliRunner()

def test_execute_read_on_complex_file_formats_correctly():
    """
    Verifies that reading a complex, multi-line file results in a
    correctly formatted YAML report with a literal block.
    This is a regression test for a bug caused by PyYAML's content-sniffing.
    """
    # Use the main README.md as the complex file input
    plan_content = """
actions:
  - action: read
    path: README.md
"""
    with open("plan.yaml", "w") as f:
        f.write(plan_content)

    result = runner.invoke(app, ["execute", "plan.yaml", "--yes", "--no-copy"])
    assert result.exit_code == 0
    output = result.stdout

    # The most important assertion: check for the literal block indicator.
    assert "content: |" in output
    # Also check that it's not the incorrect, single-line escaped format.
    assert r"# TeDDy: Your Contract-First & Test-Driven Pair-Programmer\n\n" not in output
```
