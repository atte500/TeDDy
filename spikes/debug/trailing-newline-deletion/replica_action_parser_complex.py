"""Replica of action_parser_complex FIND/REPLACE parsing with the fix.

The ONLY change from src: ``find``/``replace`` text is taken verbatim from the
fence instead of being ``rstrip("\n")``-trimmed, so author-chosen trailing
newlines and blank lines in a REPLACE block survive to the adapter.
"""
from typing import Any, Optional

from teddy_executor.core.domain.models import ActionData
from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import (
    _PeekableStream,
    get_child_text,
    get_action_heading,
)
from teddy_executor.core.services.parser_metadata import (
    parse_action_metadata,
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
    # FIX: verbatim, no rstrip("\n").
    find_content = get_child_text(find_code)

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
    # FIX: verbatim, no rstrip("\n").
    replace_content = get_child_text(replace_code)

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

    from teddy_executor.core.services.parser_infrastructure import coerce_action_params

    params = coerce_action_params(
        params,
        {
            "match_all": bool,
        },
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
            "EDIT action found no valid FIND/REPLACE blocks.",
            offending_node=node,
        )
    params["edits"] = edits
    return ActionData(type="EDIT", description=description, params=params, node=node)