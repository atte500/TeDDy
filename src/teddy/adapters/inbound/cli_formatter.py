from teddy.core.domain.models import ExecutionReport, ActionResult


def _format_action_result(result: ActionResult) -> str:
    """Formats a single action result into a markdown string."""
    action = result.action
    action_type = action.action_type

    # Dictionary-based strategy for formatting the action header
    header_formatters = {
        "execute": lambda a: f"### Action: `execute` (`{getattr(a, 'command', 'N/A')}`)",
        "create_file": lambda a: f"### Action: `create_file` (`{getattr(a, 'file_path', 'N/A')}`)",
        "read": lambda a: f"### Action: `read` (`{getattr(a, 'source', 'N/A')}`)",
    }

    # Get the appropriate formatter or use a default
    formatter = header_formatters.get(
        action_type, lambda a: f"### Action: `{a.action_type}`"
    )
    header = formatter(action)

    lines = [header, f"- **Status:** {result.status}"]

    if result.output:
        lines.extend(["- **Output:**", "```", result.output.strip(), "```"])
    if result.error:
        lines.extend(["- **Error:**", "```", result.error.strip(), "```"])

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
