import os
import platform
import yaml
from dataclasses import asdict

from teddy.core.domain.models import ExecutionReport, Action


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
        log_dict = {
            "action": _action_to_dict(result.action),
            "status": result.status,
            "output": result.output if result.output is not None else None,
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
        report_dict, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
