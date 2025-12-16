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
        "edit": lambda a: f"### Action: `edit` (`{getattr(a, 'file_path', 'N/A')}`)",
    }

    # Get the appropriate formatter or use a default
    formatter = header_formatters.get(
        action_type, lambda a: f"### Action: `{a.action_type}`"
    )
    header = formatter(action)

    # MODIFIED LOGIC: Trigger on any FAILURE, not just failure with output.
    if result.status == "FAILURE":
        details_lines = ["- **Details:**", "  ```yaml", f"  status: {result.status}"]
        if result.error:
            # Ensure error message is formatted correctly within YAML
            details_lines.append(f"  error: {result.error}")

        # Conditionally add the output block only if output is not None.
        if result.output is not None:
            details_lines.append("  output: |")
            output_lines = [f"    {line}" for line in result.output.strip().split("\n")]
            details_lines.extend(output_lines)

        details_lines.append("  ```")
        return "\n".join([header] + details_lines)

    # Default formatting for all other cases
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
