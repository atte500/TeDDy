import json
import os
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

import yaml

from teddy_executor.core.domain.models import ContextResult, ExecutionReport


class LiteralBlockDumper(yaml.SafeDumper):
    """Custom YAML dumper to format multiline strings as literal blocks."""

    def represent_scalar(self, tag, value, style=None):
        if isinstance(value, str) and "\n" in value:
            style = "|"
        return super().represent_scalar(tag, value, style)


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses, enums, etc., to JSON-serializable types."""
    if is_dataclass(obj):
        # Mypy struggles to narrow the type of `obj` after the `is_dataclass`
        # check, as it can be either a type or an instance. The `asdict`
        # function only accepts instances. We ignore the type error here
        # because the recursive nature of this function processes dicts
        # from `asdict`, not raw class types.
        return to_dict(asdict(obj))  # type: ignore[arg-type]
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_dict(i) for i in obj]
    elif isinstance(obj, Enum):
        return obj.value
    elif hasattr(obj, "isoformat"):  # Handles datetime objects
        return obj.isoformat()
    return obj


def format_report_as_yaml(report: ExecutionReport) -> str:
    """Formats the full execution report into a YAML string."""
    report_dict = to_dict(report)
    # The `details` field can sometimes be a JSON string from an adapter, which
    # YAML will escape. We want to parse it into a dict so it gets formatted nicely.
    cleaned_action_logs = []
    if "action_logs" in report_dict:
        for log in report_dict["action_logs"]:
            if isinstance(log.get("details"), str):
                try:
                    log["details"] = json.loads(log["details"])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep it as a string if it's not valid JSON
            cleaned_action_logs.append(log)
        report_dict["action_logs"] = cleaned_action_logs

    return yaml.dump(report_dict, Dumper=LiteralBlockDumper, sort_keys=False, indent=2)


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
