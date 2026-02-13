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
    """Parses a single action text chunk into a dictionary."""
    log = {}

    # --- 1. Parse Heading ---
    heading_match = re.match(r"####\s*`(\w+)`.*", chunk)
    if not heading_match:
        return {}
    log["action_type"] = heading_match.group(1).upper()

    status_in_heading = re.search(r"- \*\*Status:\*\* (\w+)", chunk)
    status_in_body = re.search(r"\*\*Status:\*\*\s*(\w+)", chunk)

    if status_in_heading:
        log["status"] = status_in_heading.group(1).upper()
    elif status_in_body:
        log["status"] = status_in_body.group(1).upper()
    else:
        log["status"] = "UNKNOWN"

    # --- 2. Slice Chunk into Sections ---
    params_section = ""
    details_section = ""

    details_start_index = chunk.find("- **Details:**")
    params_start_index = chunk.find("- **Params:**")

    if params_start_index != -1:
        end_index = details_start_index if details_start_index != -1 else len(chunk)
        params_section = chunk[params_start_index:end_index]

    if details_start_index != -1:
        details_section = chunk[details_start_index:]

    # --- 3. Parse Params Section ---
    if params_section:
        single_line_match = re.search(r"`(\{.*\})`", params_section)
        if single_line_match:
            param_str = single_line_match.group(1)
            try:
                log["params"] = ast.literal_eval(param_str)
            except (ValueError, SyntaxError):
                log["params"] = {"raw": param_str}
        else:  # Multi-line
            params_dict = {}
            lines = params_section.split("\n")[1:]  # Skip the '- **Params:**' line
            for line in lines:
                line = line.strip()
                match = re.match(r"-\s*\*\*(.+?):\*\*\s*`(.+?)`", line)
                if match:
                    params_dict[match.group(1)] = match.group(2)
            if params_dict:
                log["params"] = params_dict

    # --- 4. Parse Details Section ---
    if details_section:
        single_line_dict_match = re.search(r"`(\{.*\})`", details_section)
        if single_line_dict_match:
            detail_str = single_line_dict_match.group(1)
            try:
                log["details"] = ast.literal_eval(detail_str)
            except (ValueError, SyntaxError):
                log["details"] = detail_str
        else:  # Raw string
            details_text = details_section.split(":", 1)[1].strip()
            # Strip common markdown formatting characters from the ends
            details_text = details_text.strip("`* ")
            log["details"] = details_text

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

            # The delimiter is the '####' heading. A positive lookahead `(?=...)` is used
            # to keep the delimiter as part of the next chunk.
            action_chunks = re.split(r"(?m)^\s*####\s", action_log_content)

            for chunk in action_chunks:
                if chunk.strip():
                    full_chunk_text = "#### " + chunk
                    parsed_log = _parse_action_chunk(full_chunk_text)
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
