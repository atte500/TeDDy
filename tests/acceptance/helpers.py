import ast
from contextlib import contextmanager
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, Generator, Optional

from typer.testing import CliRunner, Result

from teddy_executor.__main__ import app

runner = CliRunner()


def _convert_paths(data: Any) -> Any:
    """Recursively converts Path objects and strings to posix format."""
    if isinstance(data, Path):
        return data.as_posix()
    if isinstance(data, str):
        return data.replace("\\", "/")
    if isinstance(data, list):
        return [_convert_paths(item) for item in data]
    if isinstance(data, dict):
        return {key: _convert_paths(value) for key, value in data.items()}
    return data


def run_cli_command(
    monkeypatch, args: list[str], cwd: Path, input: Optional[str] = None
) -> Result:
    """
    Runs a teddy command using the CliRunner for in-process testing.
    """
    with monkeypatch.context() as m:
        m.chdir(cwd)
        return runner.invoke(app, args, input=input)


def run_cli_with_markdown_plan_on_clipboard(
    monkeypatch, plan_content: str, cwd: Path, user_input: Optional[str] = None
) -> Result:
    """
    Runs the teddy 'execute' command with a Markdown plan, using the canonical
    --plan-content argument for testing.
    """
    with monkeypatch.context() as m:
        m.chdir(cwd)
        args = ["execute", "--yes", "--no-copy", "--plan-content", plan_content]
        return runner.invoke(app, args, input=user_input)


def _parse_heading_and_status(chunk: str) -> Dict[str, str]:
    """Parses the action heading and status from a log chunk."""
    heading_match = re.match(r"###\s*`(\w+)`.*", chunk)
    if not heading_match:
        return {}

    action_type = heading_match.group(1).upper()
    status_match = re.search(
        r"-\s*\*\*Status:\*\*\s*(?:\n\s*-\s*)?(\w+)", chunk, re.MULTILINE
    )
    status = status_match.group(1).upper() if status_match else "UNKNOWN"
    return {"action_type": action_type, "status": status}


def _parse_params(chunk: str) -> Dict[str, str]:
    """Parses the parameters from a log chunk."""
    params_dict: Dict[str, str] = {}
    for line in chunk.split("\n"):
        match = re.match(r"-\s*\*\*(.+?):\*\*\s*(.*)", line)
        if match:
            key, value = match.group(1).strip(), match.group(2).strip()
            if key in ["Status", "Error", "Return Code", "Details"]:
                continue
            if value.startswith("`") and value.endswith("`") and len(value) > 1:
                value = value[1:-1]
            params_dict[key] = value
    return params_dict


def _parse_details(chunk: str) -> Dict[str, Any]:
    """Parses the details section from a log chunk."""
    details: Dict[str, Any] = {}

    # 1. Legacy format (Details as a dict in backticks)
    if legacy := _parse_legacy_details(chunk):
        return legacy

    # 2. Structured EXECUTE
    _parse_execute_details(chunk, details)

    # 3. CHAT_WITH_USER response
    _parse_chat_details(chunk, details)

    # 4. Generic error fallback
    if not details:
        _parse_error_details(chunk, details)

    return details


def _parse_legacy_details(chunk: str) -> Optional[Dict[str, Any]]:
    match = re.search(r"- \*\*Details:\*\* `(\{.*\})`", chunk)
    if match:
        try:
            return ast.literal_eval(match.group(1))
        except (ValueError, SyntaxError):
            pass
    return None


def _parse_execute_details(chunk: str, details: Dict[str, Any]):
    rc_match = re.search(r"- \*\*Return Code:\*\* `(\d*)`", chunk)
    if rc_match and rc_match.group(1):
        details["return_code"] = int(rc_match.group(1))

    for block in ["stdout", "stderr"]:
        match = re.search(
            rf"#### `{block}`\s*(`{{3,}})text\n(.*?)\n\1", chunk, re.DOTALL
        )
        if match:
            details[block] = match.group(2).strip()


def _parse_chat_details(chunk: str, details: Dict[str, Any]):
    match = re.search(r"#### User Response\s*(`{3,})text\n(.*?)\n\1", chunk, re.DOTALL)
    if match:
        details["response"] = match.group(2).strip()
    elif old_match := re.search(r"\*\*User Response:\*\*\s*(.*)", chunk):
        details["response"] = old_match.group(1).strip()


def _parse_error_details(chunk: str, details: Dict[str, Any]):
    pattern = r"-\s*\*\*(Error|Details):\*\*\s*(.*?)(?=\n\s*- \*\*|\n\s*#### `|$)"
    if match := re.search(pattern, chunk, re.DOTALL):
        details["error"] = match.group(2).strip().strip("`")


def _parse_action_chunk(chunk: str) -> Dict[str, Any]:
    """
    Parses a single action text chunk into a dictionary by delegating to helpers.
    """
    heading_info = _parse_heading_and_status(chunk)
    if not heading_info:
        return {}

    params = _parse_params(chunk)
    details = _parse_details(chunk)

    log: Dict[str, Any] = {**heading_info, "details": details}
    if params:
        log["params"] = params
    return log


def parse_markdown_report(stdout: str) -> Dict[str, Any]:
    """
    Parses the Markdown report from stdout into a structured dict.
    This implementation uses a robust "split-and-process" strategy.
    """
    report: Dict[str, Any] = {"run_summary": {}, "action_logs": []}

    # --- 1. Split Report into Summary and Action Log Sections ---
    # We split by '## Action Log' to separate the summary from the logs.
    parts = stdout.split("\n## Action Log")
    summary_text = parts[0]
    rest_of_report = ""
    if len(parts) > 1:
        rest_of_report = "## " + parts[1]

    # --- 2. Parse Run Summary ---
    summary_lines = summary_text.split("\n")
    for line in summary_lines:
        # This regex captures "Key: Value" from lines like "- **Key:** Value"
        match = re.match(r"-\s*\*\*(.+?):\*\*\s*(.*)", line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip()
            report["run_summary"][key] = value

    # --- 3. Parse Action Logs ---
    # Since we already split by '## Action Log', rest_of_report (if present)
    # IS the content.
    if rest_of_report:
        try:
            action_log_content = rest_of_report.replace("## Action Log", "", 1)

            # The delimiter is a '### `ACTION_TYPE`' heading (H3).
            # A positive lookahead `(?=...)` is used to keep the delimiter
            # as part of the next chunk.
            action_chunks = re.split(r"(?m)(?=^\s*###\s*`[A-Z_]+`)", action_log_content)

            for chunk in action_chunks:
                if chunk.strip():
                    # The chunk is the full text, no need to prepend anything.
                    parsed_log = _parse_action_chunk(chunk)
                    if parsed_log:
                        report["action_logs"].append(parsed_log)
        except IndexError:
            # This case is fine, means there was no content after the heading.
            pass

    return report


@contextmanager
def create_plan_file(
    content: str, extension: str = ".yml"
) -> Generator[Path, None, None]:
    """A context manager to create a temporary plan file."""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=extension, encoding="utf-8"
    ) as tmp_file:
        tmp_file.write(content)
        plan_path = Path(tmp_file.name)
    try:
        yield plan_path
    finally:
        if plan_path.exists():
            plan_path.unlink()
