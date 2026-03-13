import os
from typing import Any, List

import mistletoe
from mistletoe.block_token import (
    BlockCode,
    CodeFence,
    Heading,
    List as MdList,
    Document,
)

from teddy_executor.core.domain.models import ActionData, Plan, ActionType
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError
from teddy_executor.core.services.parser_infrastructure import (
    H1_LEVEL,
    H2_LEVEL,
    _FencePreProcessor,
    _PeekableStream,
    get_child_text,
    get_action_heading,
    print_ast,
    format_structural_mismatch_msg,
)
from teddy_executor.core.services.action_parser_strategies import (
    parse_create_action,
    parse_read_action,
    parse_edit_action,
    parse_execute_action,
    parse_research_action,
    parse_prompt_action,
    parse_prune_action,
    parse_invoke_action,
    parse_return_action,
)


class MarkdownPlanParser(IPlanParser):
    """
    A service that parses a Markdown plan string into a `Plan` domain object using a
    single-pass AST stream.
    """

    def __init__(self):
        self._preprocessor = _FencePreProcessor()
        self._valid_actions = {action.value for action in ActionType}
        self._dispatch_map = {
            "CREATE": parse_create_action,
            "READ": parse_read_action,
            "EDIT": lambda s: parse_edit_action(s, self._valid_actions),
            "EXECUTE": parse_execute_action,
            "RESEARCH": lambda s: parse_research_action(s, self._valid_actions),
            "PROMPT": lambda s: parse_prompt_action(s, self._valid_actions),
            "PRUNE": parse_prune_action,
            "INVOKE": lambda s: parse_invoke_action(s, self._valid_actions),
            "RETURN": lambda s: parse_return_action(s, self._valid_actions),
        }

    def parse(self, plan_content: str) -> Plan:
        """
        Parses the specified Markdown plan string into a structured Plan object.
        """
        if not plan_content.strip():
            raise InvalidPlanError("Plan content cannot be empty.")

        processed_content = self._preprocessor.process(plan_content)
        doc = mistletoe.Document(processed_content)

        if os.environ.get("TEDDY_DEBUG"):
            print_ast(doc)

        stream = _PeekableStream(iter(doc.children or []))

        try:
            title, rationale, metadata = self._parse_strict_top_level(stream, doc)
            actions = self._parse_actions(stream, doc)
            return Plan(
                title=title, rationale=rationale, actions=actions, metadata=metadata
            )
        except InvalidPlanError as e:
            if "--- Expected Document Structure ---" in str(e):
                raise e

            # Fallback for errors that didn't provide a structural summary
            e_nodes = getattr(e, "offending_nodes", [])
            if not e_nodes:
                raise e

            # Re-format the error using the shared infrastructure
            rich_msg = format_structural_mismatch_msg(
                doc, str(e).splitlines()[0], -1, e_nodes
            )
            raise InvalidPlanError(rich_msg) from e

    def _raise_structural_error(
        self, doc: Document, expected_name: str, mismatch_idx: int, actual_node: Any
    ):
        """Constructs and raises a detailed structural validation error."""
        offending_nodes = [actual_node] if actual_node else []
        raise InvalidPlanError(
            self._format_structural_mismatch_msg(
                doc, expected_name, mismatch_idx, actual_node
            ),
            offending_nodes=offending_nodes,
        )

    def _format_structural_mismatch_msg(
        self, doc: Document, expected: str, mismatch_idx: int, actual_node: Any
    ) -> str:
        """Wrapper for infrastructure helper to maintain internal API for tests."""
        offending_nodes = (
            actual_node if isinstance(actual_node, list) else [actual_node]
        )
        return format_structural_mismatch_msg(
            doc, expected, mismatch_idx, offending_nodes
        )

    def _consume_mandatory_node(
        self, stream: _PeekableStream, doc: Document, idx: int, expected: str, predicate
    ) -> Any:
        node = stream.peek()
        if not node or not predicate(node):
            self._raise_structural_error(doc, expected, idx, node)
        return stream.next()

    def _parse_strict_top_level(
        self, stream: _PeekableStream, doc: Document
    ) -> tuple[str, str, dict[str, str]]:
        # 0: Find H1 Title, ignoring preamble
        node = stream.peek()
        start_idx = 0
        while node and not (isinstance(node, Heading) and node.level == H1_LEVEL):
            stream.next()
            node = stream.peek()
            start_idx += 1

        if not node:
            raise InvalidPlanError(
                "Plan parsing failed: No Level 1 heading found to indicate the plan's title."
            )

        title = get_child_text(node).strip()

        self._validate_top_level_schema(doc, start_idx)

        # If we got here, the structure is correct. Consume nodes and extract data.
        stream.next()  # Title (already used)
        metadata_list_node = stream.next()
        if not metadata_list_node:
            raise InvalidPlanError(
                "Plan parsing failed: Expected metadata list missing."
            )

        metadata = {}
        list_children = getattr(metadata_list_node, "children", [])
        for item in list_children if list_children is not None else []:
            text = get_child_text(item).strip()
            if ":" in text:
                key, value = text.split(":", 1)
                metadata[key.strip("* ")] = value.strip()

        stream.next()  # H2 Rationale
        rationale_node = stream.next()
        rationale = get_child_text(rationale_node).strip()
        stream.next()  # H2 Action Plan

        return title, rationale, metadata

    def _validate_top_level_schema(self, doc: Document, start_idx: int):
        """Validates the structural schema of the top-level nodes (C901)."""
        doc_children = doc.children if doc.children is not None else []
        children = list(doc_children)
        expected_schema = [
            (
                "a List (Metadata) immediately following the title",
                lambda n: isinstance(n, MdList),
            ),
            (
                "a Level 2 Heading containing 'Rationale'",
                lambda n: (
                    isinstance(n, Heading)
                    and n.level == H2_LEVEL
                    and "Rationale" in get_child_text(n)
                ),
            ),
            (
                "a CodeFence or BlockCode containing the rationale content",
                lambda n: isinstance(n, (CodeFence, BlockCode)),
            ),
            (
                "a Level 2 Heading containing 'Action Plan'",
                lambda n: (
                    isinstance(n, Heading)
                    and n.level == H2_LEVEL
                    and "Action Plan" in get_child_text(n)
                ),
            ),
        ]

        offending_nodes = []
        primary_mismatch = None

        for i, (expected_desc, predicate) in enumerate(expected_schema):
            target_idx = start_idx + 1 + i
            actual_node = children[target_idx] if target_idx < len(children) else None

            if not actual_node or not predicate(actual_node):
                offending_nodes.append(actual_node)
                if primary_mismatch is None:
                    primary_mismatch = (expected_desc, target_idx, actual_node)

        if offending_nodes and primary_mismatch is not None:
            expected_desc, target_idx, actual_node = primary_mismatch
            error_msg = format_structural_mismatch_msg(
                doc, expected_desc, target_idx, offending_nodes
            )
            raise InvalidPlanError(error_msg, offending_nodes=offending_nodes)

    def _parse_actions(
        self, stream: _PeekableStream, doc: Document
    ) -> List[ActionData]:
        actions: List[ActionData] = []
        # 'Action Plan' heading is already consumed by _parse_strict_top_level.

        offending_nodes = []
        primary_mismatch = None

        # Parse all subsequent actions
        while stream.has_next():
            node = stream.peek()
            action_heading = get_action_heading(node, self._valid_actions)
            if not action_heading:
                # Accumulate offending node and consume it to find the next potential heading
                offending_nodes.append(node)
                if primary_mismatch is None:
                    # Capture index -1 to trigger dynamic lookup in formatter
                    primary_mismatch = ("a Level 3 Action Heading", -1, node)
                stream.next()
                continue

            stream.next()  # Consume action heading
            action_type_str = get_child_text(action_heading).strip().replace("`", "")

            if action_type_str not in self._dispatch_map:
                raise InvalidPlanError(f"Unknown action type: {action_type_str}")

            parse_method = self._dispatch_map[action_type_str]
            actions.append(parse_method(stream))

        if offending_nodes and primary_mismatch is not None:
            expected_desc, mismatch_idx, actual_node = primary_mismatch
            raise InvalidPlanError(
                format_structural_mismatch_msg(
                    doc, expected_desc, mismatch_idx, offending_nodes
                ),
                offending_nodes=offending_nodes,
            )

        return actions

    # Structural formatting logic moved to parser_infrastructure.py
