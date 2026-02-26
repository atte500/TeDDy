import os
from typing import Any, List, Optional, Iterator
from mistletoe.block_token import (
    Heading,
)
from mistletoe.span_token import InlineCode

# Constants for Markdown structure
H1_LEVEL = 1
H2_LEVEL = 2
H3_LEVEL = 3

# Constant for parsing key-value pairs
EXPECTED_KV_PARTS = 2


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
        common_roots = ("/tmp", "/etc", "/home", "/var", "/usr", "/root")
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


def extract_posix_headers(
    command_str: str,
    initial_cwd: str | None,
    initial_env: dict[str, str] | None,
) -> tuple[str, str | None, dict[str, str] | None]:
    """
    Parses `cd` and `export` directives from the start of a shell command.
    """
    cwd = initial_cwd
    env = initial_env

    lines = command_str.strip().split("\n")
    command_lines = []
    header_processed = False

    for line in lines:
        stripped_line = line.strip()
        if not header_processed and stripped_line.startswith("cd "):
            cwd = stripped_line.split(" ", 1)[1].strip()
            continue
        elif not header_processed and stripped_line.startswith("export "):
            if env is None:
                env = {}
            _, key_value_part = stripped_line.split(" ", 1)
            if "=" in key_value_part:
                key, value = key_value_part.split("=", 1)
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                env[key] = value
            continue
        else:
            header_processed = True
            command_lines.append(line)

    final_command = "\n".join(command_lines).strip()
    return final_command, cwd, env
