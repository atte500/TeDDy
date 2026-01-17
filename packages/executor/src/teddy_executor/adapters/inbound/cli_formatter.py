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
        if "\n" in s:
            return self.represent_scalar("tag:yaml.org,2002:str", s, style="|")
        return super().represent_str(s)


# Register the custom representer to handle all strings
MyRepresenter.add_representer(str, MyRepresenter.represent_str)

# --- End of Verified Fix ---


def to_dict(obj: Any) -> Any:
    """Recursively convert dataclasses, enums, etc., to JSON-serializable types."""
    if is_dataclass(obj):
        return to_dict(asdict(obj))  # type: ignore[arg-type]
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
