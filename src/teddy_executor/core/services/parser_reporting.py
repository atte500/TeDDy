from __future__ import annotations
from typing import Any, List, TYPE_CHECKING
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import (
    get_child_text,
    H2_LEVEL,
    H3_LEVEL,
)

if TYPE_CHECKING:
    from mistletoe.block_token import Document
from teddy_executor.core.utils.markdown import get_fence_for_content

# Maximum length for AST node previews in error reports
MAX_PREVIEW_LENGTH = 60


def _get_node_preview(node: Any) -> str:
    """Extracts a truncated first-line preview of a node's content."""
    content = get_child_text(node).strip() if node else ""
    first_line = content.splitlines()[0] if content else ""
    if len(first_line) > MAX_PREVIEW_LENGTH:
        return first_line[:MAX_PREVIEW_LENGTH].strip() + "..."
    return first_line


def _get_failure_cutoff_idx(
    children: List[Any], mismatch_idx: int, offending_ids: set[int]
) -> float:
    """Determines the index after which nodes should be marked as unvalidated."""
    failure_cutoff_idx = mismatch_idx if mismatch_idx != -1 else float("inf")
    if offending_ids:
        for i, node in enumerate(children):
            if id(node) in offending_ids:
                failure_cutoff_idx = min(failure_cutoff_idx, i)
                break
    return failure_cutoff_idx


def _format_expected_structure() -> str:
    """Returns the formatted 'Expected Document Structure' section."""
    lines = [
        "[000] Heading (Level 1)",
        "[001] List (Metadata)",
        "[002] Heading (Level 2: Rationale)",
        "[003] Code Block (Rationale Content)",
        "[004] Heading (Level 2: Action Plan)",
        "[005...] Heading (Level 3: Action Type)",
        "[006...] (Action-specific AST nodes)",
    ]
    content = "\n".join(lines) + "\n"
    fence = get_fence_for_content(content)
    return f"### Expected Response Structure (MRP) \n{fence}text\n{content}{fence}\n"


def format_node_name(node: Any) -> str:
    """Formats the type name of a node with relevant metadata and content preview."""
    from mistletoe.block_token import Heading, CodeFence, BlockCode

    if node is None:
        return "EOF"
    name = type(node).__name__
    if name in ("CodeFence", "BlockCode"):
        name = "Code Block"

    if isinstance(node, Heading):
        name += f" (Level {node.level})"
    elif isinstance(node, CodeFence):
        delimiter = getattr(node, "delimiter", "```")
        count = len(delimiter)
        label = "tildes" if delimiter.startswith("~") else "backticks"
        name += f" ({count} {label})"
    elif isinstance(node, BlockCode):
        name += " (indented)"

    preview = _get_node_preview(node)
    if preview:
        name += f': "{preview}"'
    return name


def _render_ast_view(
    doc: Document,
    error_ids: set[int],
    error_map: dict[int, str],
    cutoff_idx: float = float("inf"),
) -> str:
    """
    Core AST rendering logic with logical indentation. Returns raw text.
    """
    from mistletoe.block_token import Heading

    indent_level = 0
    lines = []

    for i, node in enumerate(doc.children or []):
        node_id = id(node)

        # Logical children (indented siblings) of an action (H3)
        if isinstance(node, Heading):
            if node.level <= H2_LEVEL:
                indent_level = 0
            elif node.level == H3_LEVEL:
                indent_level = 1

        is_error = node_id in error_ids
        is_unvalidated = i > cutoff_idx and not is_error

        if is_error:
            status = f"[✗] [{i:03d}]"
        elif is_unvalidated:
            status = f"[ ] [{i:03d}]"
        else:
            status = f"[✓] [{i:03d}]"

        # Truncate error message for AST trace to keep it clean
        raw_reason = error_map.get(node_id, "")
        concise_reason = raw_reason.splitlines()[0] if raw_reason else ""
        reason = f" (Error: {concise_reason})" if is_error else ""

        # Heading 1-3 are never indented. Their contents/sub-headings are.
        is_top_heading = isinstance(node, Heading) and node.level <= H3_LEVEL
        display_indent = "  " * (0 if is_top_heading else indent_level)
        n_name = format_node_name(node)
        lines.append(f"{display_indent}{status} {n_name}{reason}")

    return "\n".join(lines) + "\n"


def format_hybrid_ast_view(
    doc: Document,
    errors: List[Any],  # List[ValidationError]
) -> str:
    """
    Generates a hybrid AST visualization: surgical highlighting and logical indentation.
    """
    error_ids = {id(e.offending_node) for e in errors if e.offending_node}
    error_map = {id(e.offending_node): e.message for e in errors if e.offending_node}
    ast_text = _render_ast_view(doc, error_ids, error_map)

    fence = get_fence_for_content(ast_text)
    return f"### Plan AST with Highlighted Failures\n{fence}text\n{ast_text}{fence}\n"


def get_action_type_from_node(plan: Plan, offending_node: Any) -> str:
    """Walks back from a node to find its parent action type."""
    from mistletoe.block_token import Heading

    if not offending_node:
        return "Unknown"

    if not plan.source_doc:
        return get_child_text(offending_node).strip().replace("`", "")

    nodes = list(plan.source_doc.children or [])
    target_idx = -1
    for i, node in enumerate(nodes):
        if id(node) == id(offending_node):
            target_idx = i
            break

    if target_idx != -1:
        for i in range(target_idx, -1, -1):
            if isinstance(nodes[i], Heading) and nodes[i].level == H3_LEVEL:
                return get_child_text(nodes[i]).strip().replace("`", "")

    return get_child_text(offending_node).strip().replace("`", "")


def validate_plan_structure(doc: Document, start_idx: int):
    """Validates the structural schema of the top-level nodes."""
    from mistletoe.block_token import (
        BlockCode,
        CodeFence,
        Heading,
        List as MdList,
    )

    doc_children = doc.children if doc.children is not None else []
    children = list(doc_children)
    expected_schema = [
        (
            "a List (Metadata) immediately following the title",
            lambda n: isinstance(n, MdList),
        ),
        (
            "a Level 2 Heading containing 'Rationale'",
            lambda n: (
                isinstance(n, Heading)
                and n.level == H2_LEVEL
                and "Rationale" in get_child_text(n)
            ),
        ),
        (
            "a CodeFence or BlockCode containing the rationale content",
            lambda n: isinstance(n, (CodeFence, BlockCode)),
        ),
        (
            "a Level 2 Heading containing 'Action Plan' or 'Message'",
            lambda n: (
                isinstance(n, Heading)
                and n.level == H2_LEVEL
                and any(
                    term in get_child_text(n) for term in ["Action Plan", "Message"]
                )
            ),
        ),
    ]

    offending_nodes = []
    primary_mismatch = None

    for i, (expected_desc, predicate) in enumerate(expected_schema):
        target_idx = start_idx + 1 + i
        actual_node = children[target_idx] if target_idx < len(children) else None

        if not actual_node or not predicate(actual_node):
            offending_nodes.append(actual_node)
            if primary_mismatch is None:
                primary_mismatch = (expected_desc, target_idx, actual_node)

    if offending_nodes and primary_mismatch is not None:
        expected_desc, target_idx, actual_node = primary_mismatch
        error_msg = format_structural_mismatch_msg(
            doc, expected_desc, target_idx, offending_nodes
        )
        raise InvalidPlanError(error_msg, offending_nodes=offending_nodes)


def format_structural_mismatch_msg(
    doc: Document,
    expected: str,
    mismatch_idx: int,
    offending_nodes: List[Any],
) -> str:
    """Constructs a detailed structural validation error message."""
    primary_node = offending_nodes[0] if offending_nodes else None
    actual_name = format_node_name(primary_node)

    is_direct = expected.startswith(("a ", "an ", "## ", "### ", "Heading", "List"))
    error_header = f"Expected {expected}" if is_direct else expected

    # If mismatch_idx is -1, this is a content error, not a structural schema mismatch
    if mismatch_idx == -1:
        msg = f"Plan content is invalid: {expected}.\n\n"
    else:
        msg = f"Plan structure is invalid. {error_header}, but found {actual_name}.\n\n"

    msg += _format_expected_structure()
    msg += "\n### Actual Response Structure\n"

    children = list(doc.children) if doc.children else []
    offending_ids = {id(node) for node in offending_nodes if node is not None}
    error_map = {id_node: error_header for id_node in offending_ids}
    if mismatch_idx != -1 and mismatch_idx < len(children):
        error_ids_set = offending_ids | {id(children[mismatch_idx])}
        error_map[id(children[mismatch_idx])] = error_header
    else:
        error_ids_set = offending_ids

    cutoff = _get_failure_cutoff_idx(children, mismatch_idx, offending_ids)
    ast_text = _render_ast_view(doc, error_ids_set, error_map, cutoff)
    fence = get_fence_for_content(ast_text)
    msg += f"{fence}text\n{ast_text}{fence}\n"

    msg += "\n**Hint:** Parsing often fails due to improper Code Block Formatting.\n"
    return msg
