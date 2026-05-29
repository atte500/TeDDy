from typing import Any, Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

from teddy_executor.core.domain.models import ActionData, ActionType
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import (
    _PeekableStream,
    get_child_text,
    get_action_heading,
    consume_content_until_next_action,
)
from teddy_executor.core.services.parser_metadata import (
    parse_action_metadata,
    parse_env_from_metadata,
)


def parse_find_replace_pair(stream: _PeekableStream) -> Optional[dict[str, Any]]:
    from mistletoe.block_token import Heading, CodeFence, BlockCode

    find_heading = stream.peek()
    if not (
        isinstance(find_heading, Heading) and "FIND:" in get_child_text(find_heading)
    ):
        return None

    stream.next()
    find_code = stream.next()
    if not isinstance(find_code, (CodeFence, BlockCode)):
        raise InvalidPlanError(
            "Missing code block for FIND in EDIT action.", offending_node=find_code
        )
    find_content = get_child_text(find_code).rstrip("\n")

    replace_heading = stream.next()
    if not (
        isinstance(replace_heading, Heading)
        and "REPLACE:" in get_child_text(replace_heading)
    ):
        raise InvalidPlanError(
            "Missing REPLACE block after FIND block",
            offending_node=replace_heading,
        )

    replace_code = stream.next()
    if not isinstance(replace_code, (CodeFence, BlockCode)):
        raise InvalidPlanError(
            "Missing REPLACE block after FIND block",
            offending_node=replace_code,
        )
    replace_content = get_child_text(replace_code).rstrip("\n")

    return {
        "find": find_content,
        "replace": replace_content,
        "find_node": find_code,
    }


def parse_edit_action(
    stream: _PeekableStream, valid_actions: set[str], node: Optional[Any] = None
) -> ActionData:
    from mistletoe.block_token import List as MdList

    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(
            "EDIT action is missing metadata list.", offending_node=metadata_list
        )
    description, params = parse_action_metadata(
        metadata_list,
        link_key_map={"File Path": "path"},
        text_key_map={
            "Match All": "match_all",
        },
    )

    if "match_all" in params:
        params["match_all"] = str(params["match_all"]).lower() == "true"

    edits = []
    while stream.has_next():
        if get_action_heading(stream.peek(), valid_actions):
            break

        pair = parse_find_replace_pair(stream)
        if pair:
            edits.append(pair)
        else:
            break

    if not edits:
        raise InvalidPlanError(
            "EDIT action found no valid FIND/REPLACE blocks.",
            offending_node=node,
        )
    params["edits"] = edits
    return ActionData(type="EDIT", description=description, params=params, node=node)


def parse_execute_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
    from mistletoe.block_token import List as MdList, CodeFence

    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(
            "EXECUTE action is missing metadata list.", offending_node=metadata_list
        )

    description, params = parse_action_metadata(
        metadata_list,
        text_key_map={
            "Expected Outcome": "expected_outcome",
            "cwd": "cwd",
            "Allow Failure": "allow_failure",
            "Background": "background",
            "Timeout": "timeout",
        },
    )

    if "allow_failure" in params:
        params["allow_failure"] = params["allow_failure"].lower() == "true"

    if "background" in params:
        params["background"] = params["background"].lower() == "true"

    if "timeout" in params and params["timeout"]:
        try:
            params["timeout"] = int(params["timeout"])
        except ValueError:
            # Leave as string, ActionFactory or validation will handle it
            pass

    env_from_meta = parse_env_from_metadata(metadata_list)
    if env_from_meta:
        params["env"] = env_from_meta

    command_block = stream.next()
    if not isinstance(command_block, CodeFence):
        raise InvalidPlanError(
            "EXECUTE action is missing command code block.",
            offending_node=command_block,
        )

    params["command"] = get_child_text(command_block).strip()

    return ActionData(type="EXECUTE", description=description, params=params, node=node)


def parse_research_action(
    stream: _PeekableStream, valid_actions: set[str], node: Optional[Any] = None
) -> ActionData:
    from mistletoe.block_token import List as MdList, CodeFence

    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("RESEARCH action is missing metadata list.")

    description, _ = parse_action_metadata(metadata_list)
    content_nodes = consume_content_until_next_action(stream, valid_actions)
    queries = []
    for content_node in content_nodes:
        if isinstance(content_node, CodeFence):
            raw_content = get_child_text(content_node)
            for line in raw_content.splitlines():
                query = line.strip()
                if query:
                    queries.append(query)
    if not queries:
        raise InvalidPlanError("RESEARCH action found no query code blocks.")
    return ActionData(
        type="RESEARCH",
        description=description,
        params={"queries": queries},
        node=node,
    )


def parse_message_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
    """
    Parses a MESSAGE action by consuming all remaining nodes in the stream.
    """
    from mistletoe.markdown_renderer import MarkdownRenderer

    nodes = []
    while stream.has_next():
        nodes.append(stream.next())

    content = ""
    if nodes:
        with MarkdownRenderer() as renderer:
            rendered_parts = [renderer.render(node) for node in nodes]
            content = "".join(rendered_parts).strip()

    return ActionData(
        type=ActionType.MESSAGE,
        description="Message to user",
        params={"content": content},
        node=node,
    )
