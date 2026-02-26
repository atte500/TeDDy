from typing import Optional
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
    extract_posix_headers,
    consume_content_until_next_action,
)
from teddy_executor.core.services.parser_metadata import (
    parse_action_metadata,
    parse_env_from_metadata,
    parse_message_and_optional_resources,
)


def parse_create_action(stream: _PeekableStream) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("CREATE action is missing metadata list.")

    description, params = parse_action_metadata(
        metadata_list, link_key_map={"File Path": "path"}
    )

    code_block = stream.next()
    if not isinstance(code_block, CodeFence):
        raise InvalidPlanError("CREATE action is missing a content code block.")

    params["content"] = ""
    if code_block.children:
        children = list(code_block.children)
        if children:
            child = children[0]
            if hasattr(child, "content"):
                params["content"] = child.content.rstrip("\n")

    return ActionData(type="CREATE", description=description, params=params)


def parse_resource_action(stream: _PeekableStream, action_type: str) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(f"{action_type} action is missing metadata list.")

    description, params = parse_action_metadata(
        metadata_list, link_key_map={"Resource": "resource"}
    )

    return ActionData(type=action_type, description=description, params=params)


def parse_read_action(stream: _PeekableStream) -> ActionData:
    return parse_resource_action(stream, "READ")


def parse_prune_action(stream: _PeekableStream) -> ActionData:
    return parse_resource_action(stream, "PRUNE")


def parse_find_replace_pair(stream: _PeekableStream) -> Optional[dict[str, str]]:
    find_heading = stream.peek()
    if not (
        isinstance(find_heading, Heading) and "FIND:" in get_child_text(find_heading)
    ):
        return None

    stream.next()
    find_code = stream.next()
    if not isinstance(find_code, (CodeFence, BlockCode)):
        raise InvalidPlanError("Missing code block for FIND in EDIT action.")
    find_content = get_child_text(find_code).rstrip("\n")

    replace_heading = stream.next()
    if not (
        isinstance(replace_heading, Heading)
        and "REPLACE:" in get_child_text(replace_heading)
    ):
        raise InvalidPlanError("Missing REPLACE heading after FIND block.")

    replace_code = stream.next()
    if not isinstance(replace_code, (CodeFence, BlockCode)):
        raise InvalidPlanError("Missing code block for REPLACE in EDIT action.")
    replace_content = get_child_text(replace_code).rstrip("\n")

    return {"find": find_content, "replace": replace_content}


def parse_edit_action(stream: _PeekableStream, valid_actions: set[str]) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("EDIT action is missing metadata list.")
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
    return ActionData(type="EDIT", description=description, params=params)


def parse_return_action(stream: _PeekableStream, valid_actions: set[str]) -> ActionData:
    params = parse_message_and_optional_resources(stream, valid_actions)
    if "message" not in params:
        raise InvalidPlanError("RETURN action is missing message content.")
    return ActionData(type="RETURN", description=None, params=params)


def parse_invoke_action(stream: _PeekableStream, valid_actions: set[str]) -> ActionData:
    metadata_list = stream.peek()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("INVOKE action is missing metadata list.")

    _, params = parse_action_metadata(
        metadata_list, link_key_map={}, text_key_map={"Agent": "agent"}
    )
    message_params = parse_message_and_optional_resources(stream, valid_actions)
    params.update(message_params)

    if "message" not in params:
        raise InvalidPlanError("INVOKE action is missing message content.")
    return ActionData(type="INVOKE", description=None, params=params)


def parse_execute_action(stream: _PeekableStream) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("EXECUTE action is missing metadata list.")

    description, params = parse_action_metadata(
        metadata_list,
        text_key_map={"Expected Outcome": "expected_outcome", "cwd": "cwd"},
    )

    env_from_meta = parse_env_from_metadata(metadata_list)
    if env_from_meta:
        params["env"] = env_from_meta

    command_block = stream.next()
    if not isinstance(command_block, CodeFence):
        raise InvalidPlanError("EXECUTE action is missing command code block.")
    raw_command = get_child_text(command_block).strip()

    final_command, cwd, env = extract_posix_headers(
        raw_command, params.get("cwd"), params.get("env")
    )

    params["command"] = final_command
    if cwd is not None:
        params["cwd"] = cwd
    if env is not None:
        params["env"] = env

    return ActionData(type="EXECUTE", description=description, params=params)


def parse_research_action(
    stream: _PeekableStream, valid_actions: set[str]
) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError("RESEARCH action is missing metadata list.")

    description, _ = parse_action_metadata(metadata_list)
    content_nodes = consume_content_until_next_action(stream, valid_actions)
    queries = []
    for node in content_nodes:
        if isinstance(node, CodeFence):
            query = get_child_text(node).strip()
            if query:
                queries.append(query)
    if not queries:
        raise InvalidPlanError("RESEARCH action found no query code blocks.")
    return ActionData(
        type="RESEARCH", description=description, params={"queries": queries}
    )


def parse_chat_with_user_action(
    stream: _PeekableStream, valid_actions: set[str]
) -> ActionData:
    content_nodes = consume_content_until_next_action(stream, valid_actions)
    if not content_nodes:
        raise InvalidPlanError("CHAT_WITH_USER action is missing prompt content.")
    rendered_parts = []
    with MarkdownRenderer() as renderer:
        for node in content_nodes:
            temp_doc = Document("")
            temp_doc.children = [node]
            rendered_parts.append(renderer.render(temp_doc).strip())
    prompt = "\n\n".join(rendered_parts)
    if not prompt:
        raise InvalidPlanError("CHAT_WITH_USER action is missing prompt content.")
    return ActionData(
        type="CHAT_WITH_USER", description=None, params={"prompt": prompt}
    )
