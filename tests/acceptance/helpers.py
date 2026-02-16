import ast
from contextlib import contextmanager
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, Generator, Optional

from typer.testing import CliRunner, Result

from teddy_executor.main import app

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
    monkeypatch, plan_content: str, cwd: Path
) -> Result:
    """
    Runs the teddy 'execute' command with a Markdown plan, using the canonical
    --plan-content argument for testing.
    """
    with monkeypatch.context() as m:
        m.chdir(cwd)
        args = ["execute", "--yes", "--no-copy", "--plan-content", plan_content]
        return runner.invoke(app, args)


def _parse_action_chunk(chunk: str) -> Dict[str, Any]:
    """
    Parses a single action text chunk into a dictionary. This function is
    designed to be resilient to multiple formats and always returns a dictionary
    for the 'details' key.
    """
    log: Dict[str, Any] = {"details": {}}

    # --- 1. Parse Heading and Status ---
    heading_match = re.match(r"####\s*`(\w+)`.*", chunk)
    if not heading_match:
        return {}
    log["action_type"] = heading_match.group(1).upper()

    status_match = re.search(r"- \*\*Status:\*\* (\w+)", chunk)
    log["status"] = status_match.group(1).upper() if status_match else "UNKNOWN"

    # --- 2. Parse Params (Handles single and multi-line) ---
    params_content = ""
    params_match = re.search(
        r"-\s*\*\*Params:\*\*\s*(.*?)(?=\n- \*\*|\n#### `|$)", chunk, re.DOTALL
    )
    if params_match:
        params_content = params_match.group(1).strip()

    if params_content:
        single_line_match = re.search(r"`(\{.*\})`", params_content)
        if single_line_match:
            param_str = single_line_match.group(1)
            try:
                log["params"] = ast.literal_eval(param_str)
            except (ValueError, SyntaxError):
                log["params"] = {"raw": param_str}
        else:
            params_dict = {}
            multi_line_matches = re.findall(
                r"-\s*\*\*(.+?):\*\*\s*`(.+?)`", params_content
            )
            for key, value in multi_line_matches:
                params_dict[key] = value
            if params_dict:
                log["params"] = params_dict

    # --- 3. Parse Details (Process specific formats first, then generic) ---
    details_dict: Dict[str, Any] = {}

    # Specific: Structured EXECUTE format
    rc_match = re.search(r"- \*\*Return Code:\*\* `(\d*)`", chunk)
    if rc_match and rc_match.group(1):
        details_dict["return_code"] = int(rc_match.group(1))

    stdout_match = re.search(r"#### `stdout`\s*````text\n(.*?)\n````", chunk, re.DOTALL)
    if stdout_match:
        details_dict["stdout"] = stdout_match.group(1).strip()

    stderr_match = re.search(r"#### `stderr`\s*````text\n(.*?)\n````", chunk, re.DOTALL)
    if stderr_match:
        details_dict["stderr"] = stderr_match.group(1).strip()

    # Specific: Legacy format (Details as a dict in backticks)
    details_dict_match = re.search(r"- \*\*Details:\*\* `(\{.*\})`", chunk)
    if details_dict_match:
        try:
            details_dict.update(ast.literal_eval(details_dict_match.group(1)))
        except (ValueError, SyntaxError):
            pass

    # Generic: Multi-line Error/Details block (as a fallback)
    if not details_dict:
        error_block_match = re.search(
            r"-\s*\*\*(Error|Details):\*\*\s*(.*?)(?=\n\s*- \*\*|\n\s*#### `|$)",
            chunk,
            re.DOTALL,
        )
        if error_block_match:
            error_content = error_block_match.group(2).strip()
            if error_content.startswith("`") and error_content.endswith("`"):
                error_content = error_content[1:-1]
            details_dict["error"] = error_content

    log["details"] = details_dict
    return log


def parse_markdown_report(stdout: str) -> Dict[str, Any]:
    """
    Parses the Markdown report from stdout into a structured dict.
    This implementation uses a robust "split-and-process" strategy.
    """
    report: Dict[str, Any] = {"run_summary": {}, "action_logs": []}

    # --- 1. Split Report into Summary and Action Log Sections ---
    # We split by the first '##' heading to separate the summary from the rest.
    parts = re.split(r"\n## ", stdout, maxsplit=1)
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
    if "### Action Log" in rest_of_report:
        try:
            action_log_content = rest_of_report.split("### Action Log")[1]

            # The delimiter is a '#### `ACTION_TYPE`' heading. A positive lookahead `(?=...)`
            # is used to keep the delimiter as part of the next chunk. This prevents
            # splitting on sub-headings like '#### `stdout`'.
            action_chunks = re.split(
                r"(?m)(?=^\s*####\s*`[A-Z_]+`)", action_log_content
            )

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
