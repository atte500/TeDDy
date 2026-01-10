import os
import platform
import yaml
from dataclasses import asdict

from teddy_executor.core.domain.models import ExecutionReport, Action, ContextResult


# Custom string class to mark strings for literal block style
class _LiteralStr(str):
    pass


def _literal_presenter(dumper, data):
    """Presenter for the _LiteralStr class."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


yaml.add_representer(_LiteralStr, _literal_presenter)


def _action_to_dict(action: Action) -> dict:
    """Converts an Action dataclass object to a dictionary for YAML serialization."""
    # Convert the dataclass to a dictionary using the official helper
    params = asdict(action)

    # The action_type is a guaranteed field on all Action subclasses.
    # Pop it from the params dict to separate it.
    action_type = params.pop("action_type")

    return {"type": action_type, "params": params}


def format_report_as_yaml(report: ExecutionReport) -> str:
    """Formats the full execution report into a YAML string."""
    action_logs_list = []
    for result in report.action_logs:
        output = result.output
        # If output is a multi-line string, wrap it in our custom class
        if isinstance(output, str) and "\n" in output:
            output = _LiteralStr(output)

        log_dict = {
            "action": _action_to_dict(result.action),
            "status": result.status,
            "output": output if output is not None else None,
            "error": result.error if result.error is not None else None,
        }
        action_logs_list.append(log_dict)

    report_dict = {
        "run_summary": report.run_summary,
        "environment": {
            "os": platform.system(),
            "cwd": str(os.getcwd()),
        },
        "action_logs": action_logs_list,
    }

    return yaml.dump(
        report_dict,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        indent=2,
    )


def _get_file_extension(file_path: str) -> str:
    """Extracts the file extension for code block formatting."""
    # A basic implementation for common file types
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

    # Section 1: System Information
    output_parts.append("# System Information")
    for key, value in sorted(context.system_info.items()):
        if key != "python_version":  # Exclude python_version as per requirements
            output_parts.append(f"{key}: {value}")

    # Section 2: Repository Tree
    output_parts.append("\n# Repository Tree")
    output_parts.append(context.repo_tree)

    # Section 3: Context Vault
    output_parts.append("\n# Context Vault")
    output_parts.extend(sorted(context.context_vault_paths))

    # Section 4: File Contents
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
