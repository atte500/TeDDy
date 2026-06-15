from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any, List, Optional

if TYPE_CHECKING:
    from mistletoe.block_token import (
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
    consume_content_until_next_action,
    normalize_headings,
    print_ast,
)
from teddy_executor.core.services.parser_reporting import (
    format_structural_mismatch_msg,
    validate_plan_structure,
)
from teddy_executor.core.services.parser_metadata import parse_plan_metadata
from teddy_executor.core.services.action_parser_strategies import (
    parse_create_action,
    parse_read_action,
)
from teddy_executor.core.services.action_parser_complex import (
    parse_edit_action,
    parse_execute_action,
    parse_research_action,
    parse_message_action,
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
            "EDIT": lambda s, node=None: parse_edit_action(
                s, self._valid_actions, node=node
            ),
            "EXECUTE": parse_execute_action,
            "RESEARCH": lambda s, node=None: parse_research_action(
                s, self._valid_actions, node=node
            ),
        }

    def parse(self, plan_content: str, plan_path: Optional[str] = None) -> Plan:
        """
        Parses the specified Markdown plan string into a structured Plan object.
        """
        from mistletoe.block_token import (
            Document,
        )

        # Trim trailing whitespace to prevent mistletoe from
        # interpreting trailing indentation as an unexpected code block.
        # We keep leading whitespace for potential Markdown significance (though rare at top-level).
        clean_content = plan_content.rstrip()

        if not clean_content:
            raise InvalidPlanError("Plan content cannot be empty.")

        # Strip preamble (text before the first # heading at start of a line)
        # Use MULTILINE so ^ matches start of any line. Allow optional leading whitespace
        # before # because Markdown permits up to 3 spaces before heading markers.
        h1_match = re.search(r"^[ \t]*#", clean_content, re.MULTILINE)
        if h1_match and h1_match.start() > 0:
            clean_content = clean_content[h1_match.start() :]

        # Normalize H1 heading on the first line (e.g., #Title -> # Title)
        # This runs after preamble stripping so it always targets the heading line
        clean_content = normalize_headings(clean_content)

        processed_content = self._preprocessor.process(clean_content)
        doc = Document(processed_content)

        if os.environ.get("TEDDY_DEBUG"):
            print_ast(doc)

        stream = _PeekableStream(iter(doc.children or []))

        try:
            title, rationale, metadata, section_heading = self._parse_strict_top_level(
                stream, doc
            )

            self._validate_mutual_exclusivity(doc)

            actions = self._parse_section_content(
                stream, clean_content, section_heading, doc
            )

            is_session = False
            if plan_path:
                normalized_path = plan_path.replace("\\", "/").lower()
                is_session = ".teddy/sessions/" in normalized_path

            plan = Plan(
                title=title,
                rationale=rationale,
                actions=actions,
                metadata=metadata,
                source_doc=doc,
                is_session=is_session,
                plan_path=plan_path,
                raw_content=clean_content,
            )

            # Write corrected content back to source file if it came from a session file path
            if plan_path and is_session:
                from pathlib import Path

                path_obj = Path(plan_path)
                try:
                    current_disk = path_obj.read_text(encoding="utf-8")
                except Exception:
                    current_disk = None
                if current_disk is not None and current_disk.rstrip() != clean_content:
                    path_obj.write_text(clean_content, encoding="utf-8")

            return plan
        except InvalidPlanError as e:
            if "### Expected Response Structure (MRP) " in str(e):
                raise e

            # Re-format the error using the shared infrastructure to always include AST
            e_nodes = getattr(e, "offending_nodes", [])
            rich_msg = format_structural_mismatch_msg(
                doc, str(e).splitlines()[0], -1, e_nodes
            )
            raise InvalidPlanError(rich_msg, offending_nodes=e_nodes) from e

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
    ) -> tuple[str, str, dict[str, str], Any]:
        from mistletoe.block_token import Heading

        # 0: Find H1 Title. Must be at index 0 per Rule 3.1.
        node = stream.peek()
        start_idx = 0

        if not node or not (isinstance(node, Heading) and node.level == H1_LEVEL):
            offending_nodes = [node] if node else []
            rich_msg = format_structural_mismatch_msg(
                doc, "a Level 1 Heading (Title)", 0, offending_nodes
            )
            raise InvalidPlanError(rich_msg, offending_nodes=offending_nodes)

        title = get_child_text(node).strip()

        validate_plan_structure(doc, start_idx)

        # If we got here, the structure is correct. Consume nodes and extract data.
        stream.next()  # Title (already used)
        metadata_list_node = stream.next()
        if not metadata_list_node:
            raise InvalidPlanError(
                "Plan parsing failed: Expected metadata list missing."
            )

        metadata = parse_plan_metadata(metadata_list_node)

        stream.next()  # H2 Rationale
        rationale_node = stream.next()
        rationale = get_child_text(rationale_node).strip()
        section_heading = stream.next()  # H2 Action Plan or Message

        return title, rationale, metadata, section_heading

    def _validate_mutual_exclusivity(self, doc: "Document") -> None:
        """Validates that the document does not contain both ## Action Plan and ## Message."""
        from mistletoe.block_token import Heading

        doc_children = doc.children or []
        h2_headings = [
            n for n in doc_children if isinstance(n, Heading) and n.level == H2_LEVEL
        ]
        h2_texts = [get_child_text(h) for h in h2_headings]
        if "Action Plan" in h2_texts and "Message" in h2_texts:
            raise InvalidPlanError(
                "Plan cannot contain both '## Action Plan' and '## Message'. Mutual exclusivity is required."
            )

    def _parse_section_content(
        self,
        stream: _PeekableStream,
        clean_content: str,
        section_heading: Any,
        doc: Document,
    ) -> List[ActionData]:
        """Parses the content of either a ## Message or ## Action Plan section."""
        section_name = get_child_text(section_heading).strip()
        if "Message" in section_name:
            raw_content = None
            start_line = getattr(section_heading, "line_number", None)
            if start_line is not None and start_line > 0:
                lines = clean_content.splitlines(keepends=True)
                if start_line < len(lines):
                    raw_content = "".join(lines[start_line:]).lstrip("\n")
            actions = [
                parse_message_action(
                    stream, node=section_heading, raw_content=raw_content
                )
            ]
        else:
            actions = self._parse_actions(stream, doc)
        return actions

    def _parse_actions(
        self, stream: _PeekableStream, doc: Document
    ) -> List[ActionData]:
        from mistletoe.block_token import BlockCode, CodeFence, ThematicBreak

        actions: List[ActionData] = []
        # 'Action Plan' heading is already consumed by _parse_strict_top_level.

        # Parse all subsequent actions
        while stream.has_next():
            node = stream.peek()
            action_heading = get_action_heading(node, self._valid_actions)

            if not action_heading:
                # Skip code blocks and thematic breaks that can appear between
                # action blocks due to formatting or trailing content.
                if isinstance(node, (BlockCode, CodeFence, ThematicBreak)):
                    stream.next()
                    continue

                # Accumulate offending node and raise structural error
                offending_nodes = consume_content_until_next_action(
                    stream, self._valid_actions
                )
                raise InvalidPlanError(
                    format_structural_mismatch_msg(
                        doc, "a Level 3 Action Heading", -1, offending_nodes
                    ),
                    offending_nodes=offending_nodes,
                )

            stream.next()  # Consume action heading
            action_type_str = get_child_text(action_heading).strip().replace("`", "")

            # Guard: MESSAGE under ## Action Plan must produce a clear mutual exclusivity error
            if action_type_str == "MESSAGE":
                raise InvalidPlanError(
                    "MESSAGE action is not allowed under '## Action Plan'. "
                    "Use '## Message' section instead. Mutual exclusivity is required.",
                    offending_nodes=[action_heading],
                )

            if action_type_str not in self._dispatch_map:
                raise InvalidPlanError(
                    f"Unknown action type: {action_type_str}",
                    offending_nodes=[action_heading],
                )

            parse_method = self._dispatch_map[action_type_str]
            actions.append(parse_method(stream, node=action_heading))

        return actions

    # Structural formatting logic moved to parser_infrastructure.py
