from typing import Any, List, Optional
from mistletoe.block_token import (
    Document,
    List as MdList,
    ListItem as MdListItem,
)
from mistletoe.markdown_renderer import MarkdownRenderer
from mistletoe.span_token import Link

from teddy_executor.core.services.parser_infrastructure import (
    EXPECTED_KV_PARTS,
    _PeekableStream,
    get_child_text,
    consume_content_until_next_action,
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


def parse_handoff_resources_from_list(metadata_list: MdList) -> List[str] | None:
    """Parses handoff resources from a nested metadata list."""
    resources = []
    if not (metadata_list and metadata_list.children):
        return None

    for item in metadata_list.children:
        item_text = get_child_text(item).strip()
        if item_text.startswith("Handoff Resources:"):
            resource_list = find_node_in_tree(item, MdList)
            if resource_list and resource_list.children:
                for res_item in resource_list.children:
                    link = find_node_in_tree(res_item, Link)
                    if link:
                        target = normalize_link_target(link.target)
                        resources.append(normalize_path(target))
    return resources if resources else None


def parse_message_and_optional_resources(
    stream: _PeekableStream, valid_actions: set[str]
) -> dict[str, Any]:
    """Parses message content and optional resource lists until the next action."""
    params: dict[str, Any] = {}
    next_node = stream.peek()

    if isinstance(next_node, MdList):
        metadata_list = stream.next()
        if metadata_list:
            resources = parse_handoff_resources_from_list(metadata_list)
            if resources:
                params["handoff_resources"] = resources

    content_nodes = consume_content_until_next_action(stream, valid_actions)
    if content_nodes:
        rendered_parts = []
        with MarkdownRenderer() as renderer:
            for node in content_nodes:
                temp_doc = Document("")
                temp_doc.children = [node]
                rendered_parts.append(renderer.render(temp_doc).strip())
        message = "\n\n".join(rendered_parts)
        if message:
            params["message"] = message

    return params
