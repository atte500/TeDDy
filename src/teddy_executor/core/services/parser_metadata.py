from typing import Any, List, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mistletoe.block_token import (
        List as MdList,
        ListItem as MdListItem,
    )
    from mistletoe.span_token import Link

from teddy_executor.core.services.parser_infrastructure import (
    EXPECTED_KV_PARTS,
    get_child_text,
    normalize_path,
    normalize_link_target,
    find_node_in_tree,
)


def _extract_text_with_emphasis(node: Any) -> str:
    """
    Extract text from an AST node, emitting delimiter markers for Strong/Emphasis tokens.

    Used only for extracting the value portion of metadata key-value pairs.
    Unlike `get_child_text`, it emits `__text__` for Strong tokens and `_text_`
    for Emphasis tokens, preserving literal double underscores like those in
    `__main__.py` that mistletoe would otherwise parse as formatting.
    """
    from mistletoe.span_token import Strong, Emphasis, RawText

    if isinstance(node, RawText):
        return getattr(node, "content", "")

    if isinstance(node, Strong):
        inner = ""
        if hasattr(node, "children") and node.children:
            inner = "".join(_extract_text_with_emphasis(c) for c in node.children)
        return f"__{inner}__"

    if isinstance(node, Emphasis):
        inner = ""
        if hasattr(node, "children") and node.children:
            inner = "".join(_extract_text_with_emphasis(c) for c in node.children)
        return f"_{inner}_"

    if hasattr(node, "children") and node.children is not None:
        return "".join(_extract_text_with_emphasis(c) for c in node.children)
    return getattr(node, "content", "")


def _extract_value_after_key(item: "MdListItem", key_text: str) -> Optional[str]:
    """
    Extract the value portion of a key-value pair from an AST ListItem node,
    preserving emphasis delimiters in the value (e.g., for paths like __main__.py).

    Navigates the item's children to find the node containing the key (a Strong
    token like **Resource:**), then extracts emphasis-aware text from all subsequent
    sibling nodes. When a Strong/Emphasis token's text matches the key, we STOP
    recursion and return the remaining siblings at that level.
    """
    from mistletoe.span_token import Strong, Emphasis

    key_with_colon = f"{key_text}:"

    def find_remaining(parent) -> Optional[list[Any]]:
        if not hasattr(parent, "children") or not parent.children:
            return None
        children = list(parent.children)
        for i, child in enumerate(children):
            child_text = get_child_text(child)
            if child_text and key_with_colon in child_text:
                if isinstance(child, (Strong, Emphasis)):
                    return children[i + 1 :]
                remaining = find_remaining(child)
                if remaining is not None:
                    return remaining
        return None

    remaining_children = find_remaining(item)
    if not remaining_children:
        return None

    value_parts = []
    for child in remaining_children:
        value_parts.append(_extract_text_with_emphasis(child))
    result = "".join(value_parts).strip()
    return result if result else None


def _process_link_key(
    item: "MdListItem", text: str, key_map: dict[str, str]
) -> Optional[tuple[str, str]]:
    """Helper to process a single link-based metadata key."""
    from mistletoe.span_token import Link

    for key_text, param_key in key_map.items():
        if f"{key_text}:" in text:
            link_node = find_node_in_tree(item, Link)
            if link_node:
                target = normalize_link_target(link_node.target)
                return param_key, normalize_path(target)
            # No link found: extract value from plain text using AST-based
            # emphasis-aware extraction to preserve double underscores.
            value = _extract_value_after_key(item, key_text)
            if value is not None:
                return param_key, normalize_path(value)
            # Last resort fallback: use original (possibly corrupted) text
            parts = text.split(f"{key_text}:", 1)
            if len(parts) == EXPECTED_KV_PARTS and parts[1].strip():
                return param_key, normalize_path(parts[1].strip())
    return None


def _process_text_key(text: str, key_map: dict[str, str]) -> Optional[tuple[str, str]]:
    """Helper to process a single text-based metadata key."""
    # Strip markdown bolding for resilient key matching
    clean_text = text.replace("**", "")
    for key_text, param_key in key_map.items():
        if f"{key_text}:" in clean_text:
            # Use clean text for finding the colon and splitting
            parts = clean_text.split(":", 1)
            return param_key, parts[1].strip()
    return None


def parse_plan_metadata(metadata_list_node: "MdList") -> dict[str, str]:
    """Parses top-level plan metadata list."""
    metadata = {}
    list_children = getattr(metadata_list_node, "children", [])
    for item in list_children if list_children is not None else []:
        text = get_child_text(item).strip()
        if ":" in text:
            key, value = text.split(":", 1)
            metadata[key.strip("* ")] = value.strip()
    return metadata


def parse_action_metadata(
    metadata_list: "MdList",
    link_key_map: Optional[dict[str, str]] = None,
    text_key_map: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], dict[str, Any]]:
    """Parses metadata from a Markdown list."""
    from mistletoe.block_token import ListItem as MdListItem

    params: dict[str, Any] = {}
    description: Optional[str] = None
    if not metadata_list.children:
        return description, params

    _link_key_map = link_key_map or {}
    _text_key_map = text_key_map or {}

    for item in metadata_list.children:
        if not isinstance(item, MdListItem):
            continue
        text = get_child_text(item)

        if "Description:" in text:
            description = text.split(":", 1)[1].strip()
            continue

        link_result = _process_link_key(item, text, _link_key_map)
        if link_result:
            params[link_result[0]] = link_result[1]
            continue

        text_result = _process_text_key(text, _text_key_map)
        if text_result:
            params[text_result[0]] = text_result[1]

    return description, params


def parse_env_from_metadata(metadata_list: "MdList") -> Optional[dict[str, str]]:
    """Parses environment variables from a nested metadata list."""
    from mistletoe.block_token import List as MdList

    if not metadata_list.children:
        return None

    env_dict: dict[str, str] = {}
    for item in metadata_list.children:
        if "env:" in get_child_text(item).strip():
            env_list = find_node_in_tree(item, MdList)
            if env_list and env_list.children:
                for env_item in env_list.children:
                    env_text = get_child_text(env_item).strip()
                    if ":" in env_text:
                        key, value = [p.strip() for p in env_text.split(":", 1)]
                        env_dict[key] = value.strip('"')
    return env_dict if env_dict else None


def _find_all_links(node) -> "List[Link]":
    """Recursively finds all Link tokens in a node tree."""
    from mistletoe.span_token import Link

    links = []
    if isinstance(node, Link):
        links.append(node)
    if hasattr(node, "children") and node.children:
        for child in node.children:
            links.extend(_find_all_links(child))
    return links


def parse_handoff_resources_from_list(metadata_list: "MdList") -> "List[str] | None":
    """
    Parses handoff resources from a metadata list item.
    Supports both nested lists and simple multi-line links within the item.
    Recognizes both legacy "Handoff Resources:" and new "Reference Files:".
    """
    resources = []
    if not (metadata_list and metadata_list.children):
        return None

    for item in metadata_list.children:
        item_text = get_child_text(item).strip()
        if item_text.startswith("Handoff Resources:") or item_text.startswith(
            "Reference Files:"
        ):
            # Find all links within this list item's entire sub-tree
            links = _find_all_links(item)
            for link in links:
                target = normalize_link_target(link.target)
                resources.append(normalize_path(target))

    return resources if resources else None
