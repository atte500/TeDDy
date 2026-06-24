import os
import re
from typing import Any, List, Optional, Iterator, TYPE_CHECKING


# Insert a space after `#` on the first line if missing (e.g., `#Title` -> `# Title`)
# Only normalizes the first line to avoid corrupting code fences or shebangs.
def normalize_headings(content: str) -> str:
    """Insert a space after `#` if missing on the first line (the H1 title)."""
    first_newline = content.find("\n")
    if first_newline == -1:
        first_line = content
        rest = ""
    else:
        first_line = content[:first_newline]
        rest = content[first_newline:]
    if re.match(r"^#[^ #\t\n]", first_line):
        first_line = "# " + first_line[1:]
    return first_line + rest


if TYPE_CHECKING:
    from mistletoe.block_token import Heading

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
        """
        Pre-process raw Markdown content to normalize code fences.

        Currently handles:
        - Stripping trailing non-whitespace content on fence lines with 6+
          consecutive backticks or tildes (e.g., ``~~~~~~ trailing text`` → ``~~~~~~``).
        """
        lines = content.split("\n")
        result = []
        # Pattern: optional leading whitespace, then 6+ consecutive pure tildes
        # OR 6+ consecutive pure backticks, then any trailing content.
        pattern = re.compile(r"^(\s*)(\~{6,}|\`{6,})(.*)$")

        for line in lines:
            match = pattern.match(line)
            if match:
                trailing = match.group(3)
                # Only strip trailing content if it does NOT contain any backtick
                # or tilde.  This prevents corrupting lines like
                # "~~~~~~` trailing" where fence characters appear in content.
                if trailing is not None and trailing.strip():
                    if not any(c in trailing for c in ("`", "~")):
                        line = match.group(1) + match.group(2)
                # If trailing is empty/whitespace or contains fence chars,
                # keep original line unchanged.
            result.append(line)

        return "\n".join(result)


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


def get_action_heading(node: Any, valid_actions: set[str]) -> "Optional[Heading]":
    """Checks if a node is a valid H3 action heading."""
    from mistletoe.block_token import Heading
    from mistletoe.span_token import InlineCode

    if isinstance(node, Heading) and node.level == H3_LEVEL:
        text = get_child_text(node).strip()
        potential_type = text.split(":")[0].strip().replace("`", "")
        # Normalize: strip non-alphabetic characters so "READ**" matches "READ"
        cleaned_type = re.sub(r"[^A-Za-z]", "", potential_type)
        if cleaned_type in valid_actions:
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
    from mistletoe.block_token import Heading

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
