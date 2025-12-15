# RCA: Inconsistent Failure Report Formatting

## 1. Summary
The system produced an inconsistent failure report format for the `edit` action when the target file did not exist. The acceptance test `tests/acceptance/test_edit_action.py::test_editing_non_existent_file_fails_gracefully` correctly identified this by asserting the presence of the new YAML-style format (`status: FAILURE`) but receiving the old markdown format (`- **Status:** FAILURE`).

## 2. Investigation Summary
The investigation focused on the data flow from the `LocalFileSystemAdapter` raising a `FileNotFoundError` to the final report rendering in the `CLIFormatter`.

1.  **Hypothesis 1: `ActionResult` for `FileNotFoundError` lacks an `output` field.** This was **Confirmed**. The `PlanService` correctly handles the exception but creates an `ActionResult` where `output` is `None`.
2.  **Hypothesis 2: The `CLIFormatter`'s logic is too restrictive.** This was **Confirmed**. The condition to trigger the new YAML-style report was `if result.status == "FAILURE" and result.output:`. Because the `output` field was `None` (a falsy value), this condition failed, and the formatter used its fallback logic, producing the old format.
3.  **Hypothesis 3: The `PlanService` should be fixed.** This was **Refuted**. While a fix could be applied here, the more robust and correct solution is in the presentation layer to ensure all failures are handled consistently, regardless of their origin.

## 3. Root Cause
The definitive root cause is an incomplete conditional check in the `CLIFormatter._format_action_result` function. The logic was designed to handle failures that included file content (e.g., `SearchTextNotFoundError`) but did not correctly handle failures where no content was available (e.g., `FileNotFoundError`). This resulted in two different visual formats for failure reports, breaking the application's design principle of consistent user output.

## 4. Verified Solution
The solution is to modify `_format_action_result` in `src/teddy/adapters/inbound/cli_formatter.py` to make its failure formatting more robust. The logic should be changed to trigger the YAML-style block for *any* result with `status == "FAILURE"`, and then conditionally include the `output` key only if `result.output` is not `None`.

The following code, proven in the confirmation spike (`spikes/debug/01-verify-filenotfound-output/check_proposed_fix.py`), resolves the issue. It should replace the existing `_format_action_result` function.

```python
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
            error_msg = str(result.error).replace("'", "''")
            details_lines.append(f"  error: {error_msg}")

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
```
*Note: A small correction was added to the spike code to handle potential single quotes in error messages for valid YAML.*
