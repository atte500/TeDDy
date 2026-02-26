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
)
from teddy_executor.core.services.action_parser_strategies import (
    parse_create_action,
    parse_read_action,
    parse_edit_action,
    parse_execute_action,
    parse_research_action,
    parse_chat_with_user_action,
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
            "CHAT_WITH_USER": lambda s: parse_chat_with_user_action(
                s, self._valid_actions
            ),
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
            title = self._parse_strict_top_level(stream, doc)
            actions = self._parse_actions(stream, doc)
            return Plan(title=title, actions=actions)
        except InvalidPlanError as e:
            if "--- Expected Document Structure ---" in str(e):
                raise e

            ast_summary = []
            for i, child in enumerate(doc.children or []):
                content = get_child_text(child).strip()
                first_line = content.splitlines()[0][:50] if content else ""
                ast_summary.append(f"[{i:03d}] {type(child).__name__}: {first_line}")

            debug_info = (
                "\n\n--- AST Summary (Trace of top-level nodes) ---\n"
                + "\n".join(ast_summary)
                + "\n\n**Hint:** Parsing often fails because code blocks are not strictly nested. Try to **double** the number of backticks for your outer code blocks. "
            )
            raise InvalidPlanError(f"{str(e)}{debug_info}") from e

    def _raise_structural_error(
        self, doc: Document, expected_name: str, mismatch_idx: int, actual_node: Any
    ):
        """Constructs and raises a detailed structural validation error."""
        raise InvalidPlanError(
            self._format_structural_mismatch_msg(
                doc, expected_name, mismatch_idx, actual_node
            )
        )

    def _format_structural_mismatch_msg(
        self, doc: Document, expected: str, mismatch_idx: int, actual_node: Any
    ) -> str:
        actual_name = type(actual_node).__name__ if actual_node else "EOF"
        if isinstance(actual_node, Heading):
            actual_name += f" (Level {actual_node.level})"

        def get_preview(n):
            content = get_child_text(n).strip() if n else ""
            return content.splitlines()[0][:30].strip() if content else ""

        preview = get_preview(actual_node)
        if preview:
            actual_name += f': "{preview}..."'

        msg = f"Plan structure is invalid. Expected {expected}, but found {actual_name}.\n\n"
        msg += "--- Expected Document Structure ---\n"
        msg += "[000] Heading (Level 1)\n"
        msg += "[001] List (Metadata)\n"
        msg += "[002] Heading (Level 2: Rationale)\n"
        msg += "[003] BlockCode (Rationale Content)\n"
        msg += "[004] [Optional] Heading (Level 2: Memos)\n"
        msg += "[005] [Optional] BlockCode (Memos Content)\n"
        msg += "[006] Heading (Level 2: Action Plan)\n"
        msg += "[007...] Heading (Level 3: Action Type)\n"
        msg += "[008...] (Action-specific AST nodes)\n"

        msg += "\n--- Actual Document Structure ---\n"
        children = list(doc.children) if doc.children else []

        # If mismatch_idx is not provided, try to find the actual_node
        if mismatch_idx == -1 and actual_node:
            try:
                mismatch_idx = children.index(actual_node)
            except ValueError:
                pass

        # Print all available children up to mismatch or 20
        end_idx = (
            min(len(children), mismatch_idx + 1)
            if mismatch_idx != -1
            else min(len(children), 20)
        )

        for i in range(end_idx):
            node = children[i]
            n_name = type(node).__name__
            if isinstance(node, Heading):
                n_name += f" (Level {node.level})"

            c_prev = get_preview(node)
            if c_prev:
                n_name += f': "{c_prev}..."'

            msg += (
                f"[{i:03d}] {n_name}{'  <-- MISMATCH' if i == mismatch_idx else ''}\n"
            )

        msg += "\n**Hint:** Parsing often fails because code blocks are not strictly nested. Try to **double** the number of backticks for your outer code blocks.\n"
        return msg

    def _consume_mandatory_node(
        self, stream: _PeekableStream, doc: Document, idx: int, expected: str, predicate
    ) -> Any:
        node = stream.peek()
        if not node or not predicate(node):
            self._raise_structural_error(doc, expected, idx, node)
        return stream.next()

    def _parse_strict_top_level(self, stream: _PeekableStream, doc: Document) -> str:
        # 0: Find H1 Title, ignoring preamble
        node = stream.peek()
        actual_idx = 0
        while node and not (isinstance(node, Heading) and node.level == H1_LEVEL):
            stream.next()
            node = stream.peek()
            actual_idx += 1

        if not node:
            raise InvalidPlanError(
                "Plan parsing failed: No Level 1 heading found to indicate the plan's title."
            )

        title = get_child_text(node).strip()
        stream.next()
        actual_idx += 1

        # 1: List Metadata
        self._consume_mandatory_node(
            stream,
            doc,
            actual_idx,
            "a List (Metadata) immediately following the title",
            lambda n: isinstance(n, MdList),
        )
        actual_idx += 1

        # 2: H2 Rationale
        self._consume_mandatory_node(
            stream,
            doc,
            actual_idx,
            "a Level 2 Heading containing 'Rationale'",
            lambda n: isinstance(n, Heading)
            and n.level == H2_LEVEL
            and "Rationale" in get_child_text(n),
        )
        actual_idx += 1

        # 3: BlockCode Rationale
        self._consume_mandatory_node(
            stream,
            doc,
            actual_idx,
            "a CodeFence or BlockCode containing the rationale content",
            lambda n: isinstance(n, (CodeFence, BlockCode)),
        )
        actual_idx += 1

        # 4/5: Optional H2 Memos -> BlockCode
        node = stream.peek()
        if (
            node
            and isinstance(node, Heading)
            and node.level == H2_LEVEL
            and "Memos" in get_child_text(node)
        ):
            stream.next()
            actual_idx += 1
            self._consume_mandatory_node(
                stream,
                doc,
                actual_idx,
                "a CodeFence or BlockCode containing the memos content",
                lambda n: isinstance(n, (CodeFence, BlockCode)),
            )
            actual_idx += 1

        # 6: H2 Action Plan
        self._consume_mandatory_node(
            stream,
            doc,
            actual_idx,
            "a Level 2 Heading containing 'Action Plan'",
            lambda n: isinstance(n, Heading)
            and n.level == H2_LEVEL
            and "Action Plan" in get_child_text(n),
        )
        actual_idx += 1

        return title

    def _parse_actions(
        self, stream: _PeekableStream, doc: Document
    ) -> List[ActionData]:
        actions: List[ActionData] = []
        # 'Action Plan' heading is already consumed by _parse_strict_top_level.

        # Parse all subsequent actions
        while stream.has_next():
            node = stream.peek()
            action_heading = get_action_heading(node, self._valid_actions)
            if not action_heading:
                self._raise_structural_error(
                    doc,
                    "a Level 3 Action Heading",
                    -1,  # Find the index dynamically
                    node,
                )

            stream.next()  # Consume action heading
            action_type_str = get_child_text(action_heading).strip().replace("`", "")

            if action_type_str not in self._dispatch_map:
                raise InvalidPlanError(f"Unknown action type: {action_type_str}")

            parse_method = self._dispatch_map[action_type_str]
            actions.append(parse_method(stream))

        return actions

    # Action-specific parsing logic moved to action_parser_strategies.py

    # Action-specific parsing logic moved to action_parser_strategies.py
