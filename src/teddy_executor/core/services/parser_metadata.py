from typing import Any, List, Optional
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


def _process_link_key(
    item: MdListItem, text: str, key_map: dict[str, str]
) -> Optional[tuple[str, str]]:
    """Helper to process a single link-based metadata key."""
    for key_text, param_key in key_map.items():
        if f"{key_text}:" in text:
            link_node = find_node_in_tree(item, Link)
            if link_node:
                target = normalize_link_target(link_node.target)
                return param_key, normalize_path(target)
            parts = text.split(f"{key_text}:", 1)
            if len(parts) == EXPECTED_KV_PARTS and parts[1].strip():
                return param_key, normalize_path(parts[1].strip())
    return None


def _process_text_key(text: str, key_map: dict[str, str]) -> Optional[tuple[str, str]]:
    """Helper to process a single text-based metadata key."""
    for key_text, param_key in key_map.items():
        if f"{key_text}:" in text:
            return param_key, text.split(":", 1)[1].strip()
    return None


def parse_action_metadata(
    metadata_list: MdList,
    link_key_map: Optional[dict[str, str]] = None,
    text_key_map: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], dict[str, Any]]:
    """Parses metadata from a Markdown list."""
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


def parse_env_from_metadata(metadata_list: MdList) -> Optional[dict[str, str]]:
    """Parses environment variables from a nested metadata list."""
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


def _find_all_links(node) -> List[Link]:
    """Recursively finds all Link tokens in a node tree."""
    links = []
    if isinstance(node, Link):
        links.append(node)
    if hasattr(node, "children") and node.children:
        for child in node.children:
            links.extend(_find_all_links(child))
    return links


def parse_handoff_resources_from_list(metadata_list: MdList) -> List[str] | None:
    """
    Parses handoff resources from a metadata list item.
    Supports both nested lists and simple multi-line links within the item.
    """
    resources = []
    if not (metadata_list and metadata_list.children):
        return None

    for item in metadata_list.children:
        item_text = get_child_text(item).strip()
        if item_text.startswith("Handoff Resources:"):
            # Find all links within this list item's entire sub-tree
            links = _find_all_links(item)
            for link in links:
                target = normalize_link_target(link.target)
                resources.append(normalize_path(target))

    return resources if resources else None
