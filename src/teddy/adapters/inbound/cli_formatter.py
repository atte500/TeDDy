from teddy.core.domain.models import ExecutionReport, ActionResult


def _format_action_result(result: ActionResult) -> str:
    """Formats a single action result into a markdown string."""
    lines = []
    action_type = result.action.action_type

    if action_type == "execute":
        command = result.action.params.get("command", "N/A")
        lines.append(f"### Action: `execute` (`{command}`)")
    elif action_type == "create_file":
        file_path = result.action.params.get("file_path", "N/A")
        lines.append(f"### Action: `create_file` (`{file_path}`)")
    else:
        lines.append(f"### Action: `{action_type}`")

    lines.append(f"- **Status:** {result.status}")
    if result.output:
        lines.append("- **Output:**")
        lines.append("```")
        lines.append(result.output.strip())
        lines.append("```")
    if result.error:
        lines.append("- **Error:**")
        lines.append("```")
        lines.append(result.error.strip())
        lines.append("```")
    return "\n".join(lines)


def format_report_as_markdown(report: ExecutionReport) -> str:
    """Formats the full execution report into a markdown string."""
    lines = ["# Execution Report"]

    overall_status = report.run_summary.get("status", "UNKNOWN")
    lines.append(f"## Run Summary: {overall_status}")
    lines.append("---")

    lines.append("## Action Logs")
    for result in report.action_logs:
        lines.append(_format_action_result(result))
        lines.append("\n---")

    return "\n".join(lines)
