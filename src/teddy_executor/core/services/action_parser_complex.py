from typing import Any, Optional
from mistletoe.block_token import (
    BlockCode,
    CodeFence,
    Heading,
    List as MdList,
    Document,
)
from mistletoe.markdown_renderer import MarkdownRenderer

from teddy_executor.core.domain.models import ActionData
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
    parse_handoff_resources_from_list,
)


def parse_find_replace_pair(stream: _PeekableStream) -> Optional[dict[str, Any]]:
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
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(
            "EDIT action is missing metadata list.", offending_node=metadata_list
        )
    description, params = parse_action_metadata(
        metadata_list, link_key_map={"File Path": "path"}
    )

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
            "EDIT action found no valid FIND/REPLACE blocks. An Action or Rationale code block may be improperly nested."
        )
    params["edits"] = edits
    return ActionData(type="EDIT", description=description, params=params, node=node)


def parse_return_action(
    stream: _PeekableStream, valid_actions: set[str], node: Optional[Any] = None
) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("RETURN action is missing metadata list.")

    description, params = parse_action_metadata(metadata_list)
    resources = parse_handoff_resources_from_list(metadata_list)
    if resources:
        params["handoff_resources"] = resources

    if not description:
        raise InvalidPlanError(
            "RETURN action is missing 'Description' (message content)."
        )

    params["message"] = description
    return ActionData(type="RETURN", description=description, params=params, node=node)


def parse_invoke_action(
    stream: _PeekableStream, valid_actions: set[str], node: Optional[Any] = None
) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("INVOKE action is missing metadata list.")

    description, params = parse_action_metadata(
        metadata_list, text_key_map={"Agent": "agent"}
    )
    resources = parse_handoff_resources_from_list(metadata_list)
    if resources:
        params["handoff_resources"] = resources

    if "agent" not in params:
        raise InvalidPlanError("INVOKE action is missing 'Agent' parameter.")
    if not description:
        raise InvalidPlanError(
            "INVOKE action is missing 'Description' (message content)."
        )

    params["message"] = description
    return ActionData(type="INVOKE", description=description, params=params, node=node)


def parse_execute_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
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
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("RESEARCH action is missing metadata list.")

    description, _ = parse_action_metadata(metadata_list)
    content_nodes = consume_content_until_next_action(stream, valid_actions)
    queries = []
    for content_node in content_nodes:
        if isinstance(content_node, CodeFence):
            query = get_child_text(content_node).strip()
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


def parse_prompt_action(
    stream: _PeekableStream, valid_actions: set[str], node: Optional[Any] = None
) -> ActionData:
    content_nodes = consume_content_until_next_action(stream, valid_actions)
    if not content_nodes:
        raise InvalidPlanError("PROMPT action is missing prompt content.")

    params: dict[str, Any] = {}
    remaining_nodes = list(content_nodes)

    # Check if the first node is a metadata list
    if remaining_nodes and isinstance(remaining_nodes[0], MdList):
        metadata_list = remaining_nodes.pop(0)
        resources = parse_handoff_resources_from_list(metadata_list)
        if resources:
            params["handoff_resources"] = resources

    rendered_parts = []
    with MarkdownRenderer() as renderer:
        for content_node in remaining_nodes:
            temp_doc = Document("")
            temp_doc.children = [content_node]
            rendered_parts.append(renderer.render(temp_doc).strip())

    prompt = "\n\n".join(rendered_parts)
    if not prompt:
        if "handoff_resources" not in params:
            raise InvalidPlanError("PROMPT action is missing prompt content.")
        prompt = ""

    params["prompt"] = prompt
    return ActionData(type="PROMPT", description=None, params=params, node=node)
