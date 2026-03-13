import os
from typing import Any, List, Optional, Iterator
from mistletoe.block_token import (
    Heading,
    Document,
    CodeFence,
)
from mistletoe.span_token import InlineCode

# Constants for Markdown structure
H1_LEVEL = 1
H2_LEVEL = 2
H3_LEVEL = 3

# Constant for parsing key-value pairs
EXPECTED_KV_PARTS = 2

# Maximum length for AST node previews in error reports
MAX_PREVIEW_LENGTH = 60


class _FencePreProcessor:
    """
    A utility to pre-process raw LLM Markdown output to ensure all code fences are valid
    before parsing. This is a crucial safety net.
    """

    def process(self, content: str) -> str:
        # Placeholder for future implementation. For now, it's a pass-through.
        return content


class _PeekableStream:
    """A wrapper for an iterator to allow peeking at the next item."""

    def __init__(self, iterator: Iterator[Any]):
        self._iterator = iterator
        self._next_item: Optional[Any] = None
        self._fetch_next()

    def _fetch_next(self):
        try:
            self._next_item = next(self._iterator)
        except StopIteration:
            self._next_item = None

    def has_next(self) -> bool:
        return self._next_item is not None

    def peek(self) -> Optional[Any]:
        return self._next_item

    def next(self) -> Optional[Any]:
        current_item = self._next_item
        if current_item is not None:
            self._fetch_next()
        return current_item


def normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def normalize_link_target(target: str) -> str:
    if target.startswith(("http://", "https://")):
        return target
    is_abs = os.path.isabs(target)
    is_likely_true_absolute = False
    if os.name == "nt":
        has_drive, _ = os.path.splitdrive(target)
        if is_abs and has_drive:
            is_likely_true_absolute = True
    elif os.name == "posix" and is_abs:
        common_roots = ("/tmp", "/etc", "/home", "/var", "/usr", "/root")  # nosec B108
        if target.startswith(common_roots):
            is_likely_true_absolute = True
    if target.startswith("/") and not is_likely_true_absolute:
        return target.lstrip("/")
    return target


def find_node_in_tree(node: Any, node_type: type) -> Optional[Any]:
    if isinstance(node, node_type):
        return node
    if hasattr(node, "children") and node.children is not None:
        for child in node.children:
            found = find_node_in_tree(child, node_type)
            if found:
                return found
    return None


def get_child_text(node: Any) -> str:
    if hasattr(node, "children") and node.children is not None:
        return "".join([get_child_text(child) for child in node.children])
    return getattr(node, "content", "")


def get_action_heading(node: Any, valid_actions: set[str]) -> Optional[Heading]:
    """Checks if a node is a valid H3 action heading."""
    if isinstance(node, Heading) and node.level == H3_LEVEL:
        text = get_child_text(node).strip()
        potential_type = text.split(":")[0].strip().replace("`", "")
        if potential_type in valid_actions:
            return node
        # Allow unknown actions if they are formatted like `ACTION` to fail later
        children = list(node.children) if node.children else []
        if children and isinstance(children[0], InlineCode):
            return node
    return None


def consume_content_until_next_action(
    stream: _PeekableStream, valid_actions: set[str]
) -> List[Any]:
    """Consumes nodes from the stream until the next H3 action heading or H1/H2."""
    content_nodes = []
    while stream.has_next():
        node = stream.peek()
        if isinstance(node, Heading):
            if node.level <= H2_LEVEL:
                break
            if get_action_heading(node, valid_actions):
                break
        content_nodes.append(stream.next())
    return content_nodes


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
        "--- Expected Document Structure ---",
        "[000] Heading (Level 1)",
        "[001] List (Metadata)",
        "[002] Heading (Level 2: Rationale)",
        "[003] Code Block (Rationale Content)",
        "[004] Heading (Level 2: Action Plan)",
        "[005...] Heading (Level 3: Action Type)",
        "[006...] (Action-specific AST nodes)",
    ]
    return "\n".join(lines) + "\n"


def format_node_name(node: Any) -> str:
    """Formats the type name of a node with relevant metadata and content preview."""
    if node is None:
        return "EOF"
    name = type(node).__name__
    if name in ("CodeFence", "BlockCode"):
        name = "Code Block"

    if isinstance(node, Heading):
        name += f" (Level {node.level})"
    elif isinstance(node, CodeFence):
        backtick_count = len(getattr(node, "delimiter", "```"))
        name += f" ({backtick_count} backticks)"

    preview = _get_node_preview(node)
    if preview:
        name += f': "{preview}"'
    return name


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

    msg = f"Plan structure is invalid. {error_header}, but found {actual_name}.\n\n"
    msg += _format_expected_structure()
    msg += "\n--- Actual Document Structure ---\n"

    children = list(doc.children) if doc.children else []
    offending_ids = {id(node) for node in offending_nodes if node is not None}
    cutoff = _get_failure_cutoff_idx(children, mismatch_idx, offending_ids)

    for i, node in enumerate(children):
        n_name = format_node_name(node)
        is_mismatch = i == mismatch_idx or id(node) in offending_ids

        if is_mismatch:
            status, info = "[✗]", f" (Error: {error_header})"
        elif i > cutoff:
            status, info = "[ ]", ""
        else:
            status, info = "[✓]", ""

        msg += f"{status} [{i:03d}] {n_name}{info}\n"

    msg += "\n**Hint:** Parsing often fails due to improper Code Block Formatting.\n"
    return msg


def print_ast(token: Any, indent: int = 0):
    """Recursively prints the AST in a readable format for debugging."""
    prefix = "  " * indent
    print(f"{prefix}- {type(token).__name__}")

    content_attr = getattr(token, "content", None)
    if content_attr is not None:
        first_line = (
            str(content_attr).splitlines()[0]
            if "\n" in str(content_attr)
            else str(content_attr)
        )
        print(f'{prefix}  Content: "{first_line[:80]}"')

    children_attr = getattr(token, "children", None)
    if children_attr is not None:
        for child in children_attr:
            print_ast(child, indent + 1)


def translate_setup_commands(
    setup_str: str,
    initial_cwd: Optional[str] = None,
    initial_env: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], Optional[dict[str, str]]]:
    """
    Translates a chained setup string (e.g. 'cd dir && export FOO=bar')
    into cwd and env parameters.
    """
    cwd = initial_cwd
    env = initial_env

    parts = [p.strip() for p in setup_str.split("&&")]
    for part in parts:
        if part.startswith("cd "):
            cwd = part[3:].strip()
        elif part.startswith("export "):
            if env is None:
                env = {}
            kv_part = part[7:].strip()
            if "=" in kv_part:
                key, value = kv_part.split("=", 1)
                key = key.strip()
                value = value.strip()
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                env[key] = value

    return cwd, env
