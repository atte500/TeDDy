from typing import Any, Optional
from mistletoe.block_token import (
    CodeFence,
    List as MdList,
)

from teddy_executor.core.domain.models import ActionData
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import (
    _PeekableStream,
)
from teddy_executor.core.services.parser_metadata import (
    parse_action_metadata,
)


def parse_create_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(
            "CREATE action is missing metadata list.", offending_node=metadata_list
        )

    description, params = parse_action_metadata(
        metadata_list,
        link_key_map={"File Path": "path"},
        text_key_map={"Overwrite": "overwrite"},
    )

    if "overwrite" in params:
        params["overwrite"] = params["overwrite"].lower() == "true"

    code_block = stream.next()
    if not isinstance(code_block, CodeFence):
        raise InvalidPlanError(
            "CREATE action is missing a content code block.", offending_node=code_block
        )

    params["content"] = ""
    if code_block.children:
        children = list(code_block.children)
        if children:
            child = children[0]
            if hasattr(child, "content"):
                params["content"] = child.content.rstrip("\n")

    return ActionData(type="CREATE", description=description, params=params, node=node)


def parse_resource_action(
    stream: _PeekableStream, action_type: str, node: Optional[Any] = None
) -> ActionData:
    metadata_list = stream.next()
    if not isinstance(metadata_list, MdList):
        raise InvalidPlanError(
            f"{action_type} action is missing metadata list.",
            offending_node=metadata_list,
        )

    description, params = parse_action_metadata(
        metadata_list,
        link_key_map={"Resource": "resource", "File Path": "path_alias"},
    )

    if "path_alias" in params:
        params["resource"] = params.pop("path_alias")
        params["metadata_used_file_path_alias"] = True

    return ActionData(
        type=action_type, description=description, params=params, node=node
    )


def parse_read_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
    return parse_resource_action(stream, "READ", node=node)


def parse_prune_action(
    stream: _PeekableStream, node: Optional[Any] = None
) -> ActionData:
    return parse_resource_action(stream, "PRUNE", node=node)
