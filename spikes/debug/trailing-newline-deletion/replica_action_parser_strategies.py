"""Replica of action_parser_strategies.parse_create_action with the fix.

The ONLY change from src: ``params["content"]`` is taken verbatim from the
fence child instead of being ``rstrip("\n")``-trimmed, so author-chosen
trailing newlines and blank lines survive to the adapter.
"""
from typing import Any, Optional

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
    from mistletoe.block_token import List as MdList, CodeFence

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
        from teddy_executor.core.services.parser_infrastructure import (
            coerce_action_params,
        )

        params = coerce_action_params(params, {"overwrite": bool})

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
                # FIX: verbatim content, no rstrip("\n").
                params["content"] = child.content

    return ActionData(type="CREATE", description=description, params=params, node=node)