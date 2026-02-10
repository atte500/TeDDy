from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Any, Dict, Generator, Optional, List as PyList

import yaml
from mistletoe import Document
from mistletoe.block_token import List, Paragraph
from mistletoe.span_token import RawText, Strong
from mistletoe.token import Token
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


def parse_yaml_report(stdout: str) -> Dict[str, Any]:
    """
    Legacy helper. Wraps parse_markdown_report to maintain backward compatibility.
    Maps new Markdown keys to the old internal keys expected by legacy tests.
    """
    report = parse_markdown_report(stdout)

    # --- Compatibility Shim ---

    # 1. Map 'Overall Status' -> 'status'
    if "Overall Status" in report["run_summary"]:
        # Strip emoji and handle potential squashed text
        # e.g. "SUCCESS 🟢- **Execution..." -> "SUCCESS"
        raw_val = report["run_summary"]["Overall Status"]
        # Split by space first to get "SUCCESS"
        # If squashed like "SUCCESS-", split by "-"
        first_token = raw_val.split()[0]
        if "-" in first_token:
            first_token = first_token.split("-")[0]

        status = first_token.strip()
        # Handle new human-readable string "Validation Failed"
        if status == "Validation" or status == "VALIDATION_FAILED":
            status = "FAILURE"
        report["run_summary"]["status"] = status

    # 2. Map 'Execution Start Time' -> 'start_time'
    if "Execution Start Time" in report["run_summary"]:
        report["run_summary"]["start_time"] = report["run_summary"][
            "Execution Start Time"
        ]

    # 3. Map 'Execution End Time' -> 'end_time'
    if "Execution End Time" in report["run_summary"]:
        report["run_summary"]["end_time"] = report["run_summary"]["Execution End Time"]

    return report


def parse_markdown_report(stdout: str) -> Dict[str, Any]:
    """
    Parses the Markdown report from stdout into a structured dict using mistletoe.
    Robustly handles list items and extracts action logs.
    """
    doc = Document(stdout)
    report: Dict[str, Any] = {"run_summary": {}, "action_logs": []}
    # Ensure doc.children is treated as a list
    doc_children: PyList[Token] = list(doc.children) if doc.children else []

    # --- 1. Parse Run Summary (First List) ---
    summary_list = next(
        (child for child in doc_children if isinstance(child, List)), None
    )

    if summary_list and summary_list.children:
        # Cast children to list to avoid iterable indexing issues
        summary_items = list(summary_list.children)
        for item in summary_items:
            if not item.children:
                continue

            # Ensure item children is a list
            item_children = list(item.children)
            if not item_children:
                continue

            # Extract key-value from list item: "- **Key:** Value"
            paragraph = item_children[0]
            if not isinstance(paragraph, Paragraph) or not paragraph.children:
                continue

            p_children = list(paragraph.children)
            if len(p_children) >= 2:
                key_node = p_children[0]
                # Join all subsequent nodes as the value to handle fragmentation
                value_nodes = p_children[1:]

                if isinstance(key_node, Strong) and key_node.children:
                    strong_children = list(key_node.children)
                    key_text_node = strong_children[0]
                    if isinstance(key_text_node, RawText):
                        key = key_text_node.content.strip().rstrip(":")

                        # Reconstruct value string from all remaining nodes
                        value = ""
                        for node in value_nodes:
                            if isinstance(node, RawText):
                                value += node.content
                            elif (
                                isinstance(node, Strong) and node.children
                            ):  # Handle bold inside value
                                # cast to list for indexing
                                node_children = list(node.children)
                                # Access content safely
                                if hasattr(node_children[0], "content"):
                                    value += getattr(node_children[0], "content")

                        value = value.strip().lstrip(":").strip()
                        if value.endswith("-"):
                            value = value.rstrip("-").strip()

                        if key:
                            report["run_summary"][key] = value

    # --- 2. Parse Action Logs ---
    # Look for "### Action Log" heading
    action_log_heading_index = -1
    for i, child in enumerate(doc_children):
        if hasattr(child, "level") and child.level == 3:  # ### Heading
            if child.children:
                heading_children = list(child.children)
                if isinstance(heading_children[0], RawText):
                    if "Action Log" in heading_children[0].content:
                        action_log_heading_index = i
                        break

    if action_log_heading_index != -1:
        # Iterate through subsequent nodes to find action entries (#### `ACTION`)
        current_action: Dict[str, Any] = {}
        for i in range(action_log_heading_index + 1, len(doc_children)):
            node = doc_children[i]

            # Stop if we hit a higher-level heading (end of section)
            if hasattr(node, "level") and node.level <= 3:
                break

            # Start of new action: #### `ACTION`
            if hasattr(node, "level") and node.level == 4:
                # Save previous action if exists
                if current_action:
                    report["action_logs"].append(current_action)

                # Start new action
                action_name = "UNKNOWN"
                if node.children:
                    children_list = list(node.children)
                    # Often wrapped in inline code: `ACTION`
                    child = children_list[0]
                    # cast child to allow checking children safely
                    if hasattr(child, "children") and child.children:  # Code span
                        span_children = list(child.children)
                        if hasattr(span_children[0], "content"):
                            action_name = getattr(span_children[0], "content")
                    elif hasattr(child, "content"):  # Raw text
                        action_name = getattr(child, "content").strip("`")

                # Legacy tests expect 'action_type' in UPPERCASE usually, or matched to input
                # We provide both for compatibility
                current_action = {
                    "action": action_name.lower(),
                    "action_type": action_name.upper(),
                    "status": "UNKNOWN",
                }

            # Parse action details list
            if isinstance(node, List) and current_action and node.children:
                # Explicitly cast or iterate safely
                node_children = list(node.children)
                for item in node_children:
                    if not item.children:
                        continue
                    item_children = list(item.children)
                    if not item_children:
                        continue

                    paragraph = item_children[0]
                    if not isinstance(paragraph, Paragraph) or not paragraph.children:
                        continue

                    p_children = list(paragraph.children)
                    if len(p_children) >= 2:
                        key_node = p_children[0]
                        val_nodes = p_children[1:]

                        if isinstance(key_node, Strong) and key_node.children:
                            # Use a helper to extract text recursively from any token
                            def extract_text(token: Any) -> str:
                                if hasattr(token, "content") and token.content:
                                    return str(token.content)
                                if hasattr(token, "children") and token.children:
                                    return "".join(
                                        extract_text(child) for child in token.children
                                    )
                                return ""

                            k_text = extract_text(key_node).strip().rstrip(":")

                            val_text = "".join(
                                extract_text(v_node) for v_node in val_nodes
                            )
                            val_text = val_text.strip().lstrip(":").strip()

                            # Case-insensitive matching and strip
                            k_clean = k_text.lower()

                            if k_clean == "status":
                                # Handle potential squashed lines or extra text
                                current_action["status"] = val_text.split()[0].strip()
                            elif k_clean == "details":
                                # Try to parse stringified dicts for legacy compatibility
                                import ast

                                try:
                                    current_action["details"] = ast.literal_eval(
                                        val_text
                                    )
                                except (ValueError, SyntaxError):
                                    current_action["details"] = val_text
                            elif k_clean == "params":
                                import ast

                                try:
                                    current_action["params"] = ast.literal_eval(
                                        val_text
                                    )
                                except (ValueError, SyntaxError):
                                    current_action["params"] = val_text

        # Append the last action
        if current_action:
            report["action_logs"].append(current_action)

    return report


def run_cli_with_plan(monkeypatch, plan_structure: list | dict, cwd: Path) -> Result:
    """
    Runs the teddy 'execute' command with a plan structure using CliRunner.
    """
    sanitized_structure = _convert_paths(plan_structure)
    plan_content = yaml.dump(sanitized_structure, width=float("inf"))
    with monkeypatch.context() as m:
        m.chdir(cwd)
        return runner.invoke(
            app, ["execute", "--plan-content", plan_content, "--yes", "--no-copy"]
        )


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
