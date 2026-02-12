from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import Any, Dict, Generator, Optional, List as PyList

from mistletoe import Document
from mistletoe.block_token import List, Paragraph
from mistletoe.span_token import RawText, Strong
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


def parse_markdown_report(stdout: str) -> Dict[str, Any]:
    """
    Parses the Markdown report from stdout into a structured dict using mistletoe.
    Robustly handles list items and extracts action logs.
    """
    doc = Document(stdout)
    report: Dict[str, Any] = {"run_summary": {}, "action_logs": []}
    doc_children: PyList[Any] = list(doc.children) if doc.children else []

    # --- 1. Parse Run Summary (First List) ---
    summary_list = next(
        (child for child in doc_children if isinstance(child, List)), None
    )

    if summary_list and summary_list.children:
        summary_items = list(summary_list.children)
        for item in summary_items:
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
                value_nodes = p_children[1:]

                if isinstance(key_node, Strong) and key_node.children:
                    strong_children = list(key_node.children)
                    key_text_node = strong_children[0]
                    if isinstance(key_text_node, RawText):
                        key = key_text_node.content.strip().rstrip(":")
                        value = ""
                        for node in value_nodes:
                            if isinstance(node, RawText):
                                value += node.content
                            elif isinstance(node, Strong) and node.children:
                                node_children = list(node.children)
                                if hasattr(node_children[0], "content"):
                                    value += getattr(node_children[0], "content")
                        value = value.strip().lstrip(":").strip()
                        if value.endswith("-"):
                            value = value.rstrip("-").strip()
                        if key:
                            report["run_summary"][key] = value

    # --- 1.5 Parse Resource Contents ---
    resource_contents = {}
    resource_contents_heading_index = -1
    for i, child in enumerate(doc_children):
        if (
            hasattr(child, "level")
            and child.level == 2
            and child.children
            and isinstance(list(child.children)[0], RawText)
            and "Resource Contents" in list(child.children)[0].content
        ):
            resource_contents_heading_index = i
            break

    if resource_contents_heading_index != -1:

        def extract_text(token: Any) -> str:
            if hasattr(token, "content") and token.content is not None:
                return str(token.content)
            if hasattr(token, "children") and token.children:
                return "".join(extract_text(c) for c in token.children)
            return ""

        for i in range(resource_contents_heading_index + 1, len(doc_children)):
            node = doc_children[i]
            if hasattr(node, "level") and node.level <= 2:
                break
            if hasattr(node, "language"):
                resource_name = None
                for j in range(i - 1, resource_contents_heading_index, -1):
                    prev = doc_children[j]
                    if isinstance(prev, Paragraph):
                        text = extract_text(prev)
                        if "Resource:" in text:
                            parts = text.split("Resource:", 1)
                            if len(parts) > 1:
                                resource_name = parts[1].strip().strip("`")
                                break
                    if hasattr(prev, "language") or (
                        hasattr(prev, "level") and prev.level <= 2
                    ):
                        break
                if resource_name and node.children:
                    content = list(node.children)[0].content if node.children else ""
                    resource_contents[resource_name] = content.strip()

    # --- 2. Parse Action Logs ---
    action_log_heading_index = -1
    for i, child in enumerate(doc_children):
        if (
            hasattr(child, "level")
            and child.level == 3
            and child.children
            and isinstance(list(child.children)[0], RawText)
            and "Action Log" in list(child.children)[0].content
        ):
            action_log_heading_index = i
            break

    if action_log_heading_index != -1:
        current_action: Dict[str, Any] = {}
        for i in range(action_log_heading_index + 1, len(doc_children)):
            node = doc_children[i]
            if hasattr(node, "level") and node.level <= 3:
                break
            if hasattr(node, "level") and node.level == 4:
                if current_action:
                    report["action_logs"].append(current_action)
                action_name = "UNKNOWN"
                if node.children:
                    children_list = list(node.children)
                    child = children_list[0]
                    if hasattr(child, "children") and child.children:
                        span_children = list(child.children)
                        if hasattr(span_children[0], "content"):
                            action_name = getattr(span_children[0], "content")
                    elif hasattr(child, "content"):
                        action_name = getattr(child, "content").strip("`")
                current_action = {
                    "action": action_name.lower(),
                    "action_type": action_name.upper(),
                    "status": "UNKNOWN",
                }
            if isinstance(node, List) and current_action and node.children:
                node_children = list(node.children)

                def extract_text(token: Any) -> str:
                    if hasattr(token, "content") and token.content:
                        return str(token.content)
                    if hasattr(token, "children") and token.children:
                        return "".join(extract_text(child) for child in token.children)
                    return ""

                for item in node_children:
                    if not item.children:
                        continue
                    item_children = list(item.children)
                    action_paragraph = next(
                        (
                            child
                            for child in item_children
                            if isinstance(child, Paragraph)
                        ),
                        None,
                    )
                    if not action_paragraph or not action_paragraph.children:
                        continue
                    p_children = list(action_paragraph.children)
                    if (
                        not p_children
                        or not isinstance(p_children[0], Strong)
                        or not p_children[0].children
                    ):
                        continue
                    key_node = p_children[0]
                    k_text = extract_text(key_node).strip().rstrip(":")
                    k_clean = k_text.lower()
                    if k_clean == "params":
                        params_dict = {}
                        nested_list = next(
                            (
                                child
                                for child in item_children
                                if isinstance(child, List)
                            ),
                            None,
                        )
                        if nested_list and nested_list.children:
                            for param_item in nested_list.children:
                                param_item_children = (
                                    list(param_item.children)
                                    if param_item.children
                                    else []
                                )
                                if param_item_children and isinstance(
                                    param_item_children[0], Paragraph
                                ):
                                    param_para = param_item_children[0]
                                    param_p_children = (
                                        list(param_para.children)
                                        if param_para.children
                                        else []
                                    )
                                    if len(param_p_children) >= 2 and isinstance(
                                        param_p_children[0], Strong
                                    ):
                                        param_key_node = param_p_children[0]
                                        param_val_nodes = param_p_children[1:]
                                        param_key = (
                                            extract_text(param_key_node)
                                            .strip()
                                            .rstrip(":")
                                        )
                                        param_val = (
                                            "".join(
                                                extract_text(v) for v in param_val_nodes
                                            )
                                            .strip()
                                            .lstrip(":")
                                            .strip()
                                            .strip("`")
                                        )
                                        params_dict[param_key] = param_val
                        else:
                            val_nodes = p_children[1:]
                            val_text = (
                                "".join(extract_text(v_node) for v_node in val_nodes)
                                .strip()
                                .lstrip(":")
                                .strip()
                            )
                            import ast

                            val_text = val_text.strip("`")
                            try:
                                params_dict = ast.literal_eval(val_text)
                            except (ValueError, SyntaxError):
                                params_dict = {"raw": val_text}
                        current_action["params"] = params_dict
                    else:
                        val_nodes = p_children[1:]
                        val_text = (
                            "".join(extract_text(v_node) for v_node in val_nodes)
                            .strip()
                            .lstrip(":")
                            .strip()
                        )
                        if k_clean == "status":
                            current_action["status"] = val_text.split()[0].strip()
                        elif k_clean == "details":
                            import ast

                            val_text = val_text.strip("`")
                            try:
                                current_action["details"] = ast.literal_eval(val_text)
                            except (ValueError, SyntaxError):
                                current_action["details"] = val_text
        if current_action:
            report["action_logs"].append(current_action)

    # --- 3. Re-hydrate READ actions with content ---
    for log in report["action_logs"]:
        if log.get("action_type") == "READ" and log.get("status") == "SUCCESS":
            params = log.get("params", {})
            resource_key = None
            if isinstance(params, dict):
                resource_key = params.get("Resource") or params.get("resource")
            if resource_key and resource_key in resource_contents:
                if "details" not in log:
                    log["details"] = {}
                if isinstance(log["details"], str):
                    log["details"] = {"original": log["details"]}
                log["details"]["content"] = resource_contents[resource_key]

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
