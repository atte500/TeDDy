import os
from typing import Any, Dict, List, Optional, Iterator

import mistletoe
from mistletoe.block_token import (
    BlockCode,
    CodeFence,
    Heading,
    List as MdList,
    Document,
    ThematicBreak,
)
from mistletoe.markdown_renderer import MarkdownRenderer
from mistletoe.span_token import Link, InlineCode

from teddy_executor.core.domain.models import ActionData, Plan, ActionType
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser, InvalidPlanError


class _FencePreProcessor:
    """
    A utility to pre-process raw LLM Markdown output to ensure all code fences are valid
    before parsing. This is a crucial safety net.
    """

    def process(self, content: str) -> str:
        # Placeholder for future implementation. For now, it's a pass-through.
        return content


class _PeekableStream:
    """A wrapper for an iterator to allow peeking at the next item."""

    def __init__(self, iterator: Iterator[Any]):
        self._iterator = iterator
        self._next_item: Optional[Any] = None
        self._fetch_next()

    def _fetch_next(self):
        try:
            self._next_item = next(self._iterator)
        except StopIteration:
            self._next_item = None

    def has_next(self) -> bool:
        return self._next_item is not None

    def peek(self) -> Optional[Any]:
        return self._next_item

    def next(self) -> Optional[Any]:
        current_item = self._next_item
        if current_item is not None:
            self._fetch_next()
        return current_item


class MarkdownPlanParser(IPlanParser):
    """
    A service that parses a Markdown plan string into a `Plan` domain object using a
    single-pass AST stream.
    """

    def __init__(self):
        self._preprocessor = _FencePreProcessor()
        self._dispatch_map = {
            "CREATE": self._parse_create_action,
            "READ": self._parse_read_action,
            "EDIT": self._parse_edit_action,
            "EXECUTE": self._parse_execute_action,
            "RESEARCH": self._parse_research_action,
            "CHAT_WITH_USER": self._parse_chat_with_user_action,
            "PRUNE": self._parse_prune_action,
            "INVOKE": self._parse_invoke_action,
            "RETURN": self._parse_return_action,
        }
        self._valid_actions = {action.value for action in ActionType}

    def parse(self, plan_content: str) -> Plan:
        """
        Parses the specified Markdown plan string into a structured Plan object.
        """
        if not plan_content.strip():
            raise InvalidPlanError("Plan content cannot be empty.")

        processed_content = self._preprocessor.process(plan_content)
        doc = mistletoe.Document(processed_content)

        stream = _PeekableStream(iter(doc.children or []))

        try:
            title = self._parse_title(stream)
            actions = self._parse_actions(stream)
            return Plan(title=title, actions=actions)
        except InvalidPlanError as e:
            ast_summary = []
            for i, child in enumerate(doc.children or []):
                content = self._get_child_text(child).strip()
                first_line = content.splitlines()[0][:50] if content else ""
                ast_summary.append(f"[{i:03d}] {type(child).__name__}: {first_line}")

            debug_info = (
                "\n\n--- AST Summary (Trace of top-level nodes) ---\n"
                + "\n".join(ast_summary)
                + "\n\n**Hint:** Parsing often fails because code blocks are not strictly nested. "
                "Try to **double** the number of backticks for your outer code blocks. "
            )
            raise InvalidPlanError(f"{str(e)}{debug_info}") from e

    def _parse_title(self, stream: _PeekableStream) -> str:
        """Finds and returns the text of the first H1 heading from the stream."""
        while stream.has_next():
            node = stream.peek()
            if isinstance(node, Heading) and node.level == 1:
                stream.next()  # Consume the node
                return self._get_child_text(node).strip()
            # Consume non-H1 nodes before the title
            stream.next()
        return "Untitled Plan"

    def _parse_actions(self, stream: _PeekableStream) -> List[ActionData]:
        """Finds and parses all action blocks within the 'Action Plan' section."""
        actions: List[ActionData] = []
        # Find 'Action Plan' heading
        while stream.has_next():
            node = stream.peek()
            if (
                isinstance(node, Heading)
                and node.level == 2
                and "Action Plan" in self._get_child_text(node)
            ):
                stream.next()  # Consume 'Action Plan' heading
                break
            stream.next()
        else:
            raise InvalidPlanError("Plan is missing '## Action Plan' heading.")

        # Parse all subsequent actions
        while stream.has_next():
            node = stream.peek()
            if isinstance(node, ThematicBreak):
                stream.next()  # Consume and ignore separator
                continue

            action_heading = self._get_action_heading(node)
            if action_heading:
                stream.next()  # Consume action heading
                action_type_str = (
                    self._get_child_text(action_heading).strip().replace("`", "")
                )

                if action_type_str not in self._dispatch_map:
                    raise InvalidPlanError(f"Unknown action type: {action_type_str}")

                parse_method = self._dispatch_map[action_type_str]
                actions.append(parse_method(stream))
                continue

            # If we are here, we have found content that is not a valid action or separator
            error_content = self._get_child_text(node).strip().splitlines()
            first_line = error_content[0][:100] if error_content else ""
            raise InvalidPlanError(
                f"Unexpected content found between actions. "
                f"Found unexpected {type(node).__name__} "
                f"with content: '{first_line}...'.\n"
                f"**Hint:** An Action or Rationale code block may be improperly nested."
            )

        return actions

    def _get_action_heading(self, node: Any) -> Optional[Heading]:
        """Checks if a node is a valid H3 action heading."""
        if isinstance(node, Heading) and node.level == 3:
            text = self._get_child_text(node).strip()
            potential_type = text.split(":")[0].strip().replace("`", "")
            if potential_type in self._valid_actions:
                return node
            # Allow unknown actions if they are formatted like `ACTION` to fail later
            children = list(node.children) if node.children else []
            if children and isinstance(children[0], InlineCode):
                return node
        return None

    def _consume_content_until_next_action(self, stream: _PeekableStream) -> List[Any]:
        """Consumes nodes from the stream until the next H3 action heading or H1/H2."""
        content_nodes = []
        while stream.has_next():
            node = stream.peek()
            if isinstance(node, Heading):
                if node.level <= 2:
                    break
                if self._get_action_heading(node):
                    break
            content_nodes.append(stream.next())
        return content_nodes

    def _parse_create_action(self, stream: _PeekableStream) -> ActionData:
        """Parses a CREATE action block from the stream."""
        metadata_list = stream.next()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("CREATE action is missing metadata list.")

        description, params = self._parse_action_metadata(
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

    def _parse_resource_action(
        self, stream: _PeekableStream, action_type: str
    ) -> ActionData:
        """Parses a generic resource-based action block (e.g., READ, PRUNE)."""
        metadata_list = stream.next()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError(f"{action_type} action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list, link_key_map={"Resource": "resource"}
        )

        if description:
            params["Description"] = description

        return ActionData(type=action_type, description=description, params=params)

    def _parse_read_action(self, stream: _PeekableStream) -> ActionData:
        return self._parse_resource_action(stream, "READ")

    def _parse_prune_action(self, stream: _PeekableStream) -> ActionData:
        return self._parse_resource_action(stream, "PRUNE")

    def _parse_edit_action(self, stream: _PeekableStream) -> ActionData:
        metadata_list = stream.next()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("EDIT action is missing metadata list.")
        description, params = self._parse_action_metadata(
            metadata_list, link_key_map={"File Path": "path"}
        )

        content_nodes = self._consume_content_until_next_action(stream)
        edits = []
        state = "AWAITING_FIND_HEADING"
        current_find_content: Optional[str] = None

        for node in content_nodes:
            if state == "AWAITING_FIND_HEADING":
                if isinstance(node, Heading) and "FIND:" in self._get_child_text(node):
                    state = "AWAITING_FIND_CODE"
            elif state == "AWAITING_FIND_CODE":
                if isinstance(node, (CodeFence, BlockCode)):
                    if node.children:
                        raw_text_node = list(node.children)[0]
                        current_find_content = getattr(
                            raw_text_node, "content", ""
                        ).rstrip("\n")
                    else:
                        current_find_content = ""
                    state = "AWAITING_REPLACE_HEADING"
                elif isinstance(node, Heading):
                    state = "AWAITING_FIND_HEADING"  # Reset
            elif state == "AWAITING_REPLACE_HEADING":
                if isinstance(node, Heading) and "REPLACE:" in self._get_child_text(
                    node
                ):
                    state = "AWAITING_REPLACE_CODE"
            elif state == "AWAITING_REPLACE_CODE":
                if isinstance(node, (CodeFence, BlockCode)):
                    if current_find_content is not None:
                        if node.children:
                            raw_text_node = list(node.children)[0]
                            replace_content = getattr(
                                raw_text_node, "content", ""
                            ).rstrip("\n")
                        else:
                            replace_content = ""
                        edits.append(
                            {"find": current_find_content, "replace": replace_content}
                        )
                    state = "AWAITING_FIND_HEADING"
                    current_find_content = None
                elif isinstance(node, Heading):
                    state = "AWAITING_FIND_HEADING"

        if not edits:
            raise InvalidPlanError(
                "EDIT action found no valid FIND/REPLACE blocks. An Action or Rationale code block may be improperly nested."
            )
        params["edits"] = edits
        return ActionData(type="EDIT", description=description, params=params)

    def _parse_return_action(self, stream: _PeekableStream) -> ActionData:
        params = self._parse_message_and_optional_resources(stream)
        if "message" not in params:
            raise InvalidPlanError("RETURN action is missing message content.")
        return ActionData(type="RETURN", description=None, params=params)

    def _parse_message_and_optional_resources(
        self, stream: _PeekableStream
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        next_node = stream.peek()

        if isinstance(next_node, MdList):
            metadata_list = stream.next()
            resources = []
            if metadata_list and metadata_list.children:
                for item in metadata_list.children:
                    item_text = self._get_child_text(item).strip()
                    if item_text.startswith("Handoff Resources:"):
                        resource_list = self._find_node_in_tree(item, MdList)
                        if resource_list and resource_list.children:
                            for res_item in resource_list.children:
                                link = self._find_node_in_tree(res_item, Link)
                                if link:
                                    target = self._normalize_link_target(link.target)
                                    resources.append(self._normalize_path(target))
            if resources:
                params["handoff_resources"] = resources

        content_nodes = self._consume_content_until_next_action(stream)
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

    def _parse_invoke_action(self, stream: _PeekableStream) -> ActionData:
        metadata_list = stream.peek()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("INVOKE action is missing metadata list.")

        _, params = self._parse_action_metadata(
            metadata_list, link_key_map={}, text_key_map={"Agent": "agent"}
        )
        message_params = self._parse_message_and_optional_resources(stream)
        params.update(message_params)

        if "message" not in params:
            raise InvalidPlanError("INVOKE action is missing message content.")
        return ActionData(type="INVOKE", description=None, params=params)

    def _parse_execute_action(self, stream: _PeekableStream) -> ActionData:
        metadata_list = stream.next()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("EXECUTE action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list,
            text_key_map={"Expected Outcome": "expected_outcome", "cwd": "cwd"},
        )

        env_dict: Dict[str, str] = {}
        if metadata_list.children:
            for item in metadata_list.children:
                if "env:" in self._get_child_text(item).strip():
                    env_list = self._find_node_in_tree(item, MdList)
                    if env_list and env_list.children:
                        for env_item in env_list.children:
                            env_text = self._get_child_text(env_item).strip()
                            if ":" in env_text:
                                key, value = [p.strip() for p in env_text.split(":", 1)]
                                env_dict[key] = value.strip('"')
        if env_dict:
            params["env"] = env_dict

        command_block = stream.next()
        if not isinstance(command_block, CodeFence):
            raise InvalidPlanError("EXECUTE action is missing command code block.")
        params["command"] = self._get_child_text(command_block).strip()

        if description:
            params["Description"] = description
        return ActionData(type="EXECUTE", description=description, params=params)

    def _parse_research_action(self, stream: _PeekableStream) -> ActionData:
        metadata_list = stream.next()
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("RESEARCH action is missing metadata list.")

        description, _ = self._parse_action_metadata(metadata_list)
        content_nodes = self._consume_content_until_next_action(stream)
        queries = []
        for node in content_nodes:
            if isinstance(node, CodeFence):
                query = self._get_child_text(node).strip()
                if query:
                    queries.append(query)
        if not queries:
            raise InvalidPlanError("RESEARCH action found no query code blocks.")
        return ActionData(
            type="RESEARCH", description=description, params={"queries": queries}
        )

    def _parse_chat_with_user_action(self, stream: _PeekableStream) -> ActionData:
        content_nodes = self._consume_content_until_next_action(stream)
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

    def _parse_action_metadata(
        self,
        metadata_list: MdList,
        link_key_map: Optional[dict[str, str]] = None,
        text_key_map: Optional[dict[str, str]] = None,
    ) -> tuple[Optional[str], dict[str, Any]]:
        params: dict[str, Any] = {}
        description: Optional[str] = None
        if not metadata_list.children:
            return description, params

        _link_key_map = link_key_map or {}
        _text_key_map = text_key_map or {}

        for item in metadata_list.children:
            text = self._get_child_text(item)
            processed_item = False

            if "Description:" in text:
                description = text.split(":", 1)[1].strip()
                continue

            # Check for link keys
            for key_text, param_key in _link_key_map.items():
                if f"{key_text}:" in text:
                    link_node = self._find_node_in_tree(item, Link)
                    if link_node:
                        target = self._normalize_link_target(link_node.target)
                        params[param_key] = self._normalize_path(target)
                    else:
                        parts = text.split(f"{key_text}:", 1)
                        if len(parts) == 2 and parts[1].strip():
                            params[param_key] = self._normalize_path(parts[1].strip())
                    processed_item = True
                    break  # Found the key for this item, stop searching keys
            if processed_item:
                continue  # Move to the next list item

            # Check for text keys
            for key_text, param_key in _text_key_map.items():
                if f"{key_text}:" in text:
                    params[param_key] = text.split(":", 1)[1].strip()
                    break  # Found the key for this item, stop searching keys

        return description, params

    # --- AST Helper Methods ---

    def _normalize_path(self, path: str) -> str:
        return path.replace("\\", "/")

    def _normalize_link_target(self, target: str) -> str:
        if target.startswith(("http://", "https://")):
            return target
        is_abs = os.path.isabs(target)
        is_likely_true_absolute = False
        if os.name == "nt":
            has_drive, _ = os.path.splitdrive(target)
            if is_abs and has_drive:
                is_likely_true_absolute = True
        elif os.name == "posix" and is_abs:
            common_roots = ("/tmp", "/etc", "/home", "/var", "/usr", "/root")
            if target.startswith(common_roots):
                is_likely_true_absolute = True
        if target.startswith("/") and not is_likely_true_absolute:
            return target.lstrip("/")
        return target

    def _find_node_in_tree(self, node: Any, node_type: type) -> Optional[Any]:
        if isinstance(node, node_type):
            return node
        if hasattr(node, "children") and node.children is not None:
            for child in node.children:
                found = self._find_node_in_tree(child, node_type)
                if found:
                    return found
        return None

    def _get_child_text(self, node: Any) -> str:
        if hasattr(node, "children") and node.children is not None:
            return "".join([self._get_child_text(child) for child in node.children])
        return getattr(node, "content", "")
