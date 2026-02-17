import os
from typing import Any, Dict, List, Optional
import mistletoe
from mistletoe.block_token import (
    BlockCode,
    CodeFence,
    Heading,
    List as MdList,
    ListItem,
    Document,
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


class MarkdownPlanParser(IPlanParser):
    """
    A service that parses a Markdown plan string into a `Plan` domain object using an AST.
    """

    def __init__(self):
        self._preprocessor = _FencePreProcessor()

    def parse(self, plan_content: str) -> Plan:
        """
        Parses the specified Markdown plan string into a structured Plan object.
        """
        if not plan_content.strip():
            raise InvalidPlanError("Plan content cannot be empty.")

        processed_content = self._preprocessor.process(plan_content)
        doc = mistletoe.Document(processed_content)

        title = self._parse_title(doc)
        actions = self._parse_actions(doc)
        return Plan(title=title, actions=actions)

    def _parse_title(self, doc: Document) -> str:
        """Finds and returns the text of the first H1 heading."""
        if doc.children:
            for node in doc.children:
                if isinstance(node, Heading) and node.level == 1:
                    return self._get_child_text(node).strip()
        return "Untitled Plan"

    def _parse_actions(self, doc: Document) -> List[ActionData]:
        """Finds and parses all action blocks within the 'Action Plan' section."""
        actions: List[ActionData] = []
        action_plan_heading = self._find_heading(doc, "Action Plan")
        if not action_plan_heading:
            raise InvalidPlanError("Plan is missing '## Action Plan' heading.")

        action_headings = self._find_action_headings(doc, action_plan_heading)

        dispatch_map = {
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

        # Iterate through action headings and validate/parse each action
        for i, heading in enumerate(action_headings):
            action_type = self._get_child_text(heading).strip().replace("`", "")

            # 1. Validation: Unknown Action Type
            if action_type not in dispatch_map:
                raise InvalidPlanError(f"Unknown action type: {action_type}")

            # 2. Validation: Strict Structure (No Unexpected Content)
            # Determine the range of nodes belonging to this action
            next_heading = (
                action_headings[i + 1] if i + 1 < len(action_headings) else None
            )
            self._validate_action_structure(doc, heading, next_heading, action_type)

            # 3. Parsing
            parse_method = dispatch_map[action_type]
            actions.append(parse_method(doc, heading))

        return actions

    def _validate_action_structure(
        self,
        doc: Document,
        current_heading: Heading,
        next_heading: Optional[Heading],
        action_type: str,
    ):
        """
        Validates that the content between the current action heading and the next
        (or end of doc) strictly matches the expected structure for the action type.
        This prevents free-form text or junk from accumulating between actions.
        """
        if doc.children is None:
            return

        children_list = list(doc.children)
        try:
            start_index = children_list.index(current_heading)
        except ValueError:
            return

        end_index = (
            children_list.index(next_heading) if next_heading else len(children_list)
        )
        # Slices get the nodes strictly between the headings
        action_nodes = children_list[start_index + 1 : end_index]

        # Actions that allow free-form text (Paragraphs)
        if action_type in {"CHAT_WITH_USER", "INVOKE", "RETURN"}:
            return

        # Structured actions: Must NOT contain standalone Paragraphs or unrecognized nodes.
        # They typically consist of a Metadata List and optionally Code Blocks or Sub-Headings.
        for node in action_nodes:
            # We strictly whitelist the types of nodes allowed in structured actions.
            # - MdList: For params
            # - CodeFence/BlockCode: For content/commands
            # - Heading: For sub-headings like #### FIND / #### REPLACE
            if not isinstance(node, (MdList, CodeFence, BlockCode, Heading)):
                # We found a Paragraph or other unexpected node (like Quote, ThematicBreak, etc.)
                # This is "unexpected content".
                # Note: mistletoe parses blank lines as nothing, but text as Paragraphs.
                raise InvalidPlanError(
                    f"Unexpected content found between actions (in {action_type}). "
                    f"Found unexpected {type(node).__name__}."
                )

    def _find_action_headings(
        self, doc: Document, start_node: Heading
    ) -> List[Heading]:
        """
        Finds all H3 headings that represent actions.
        It strictly validates that the heading text matches a known action type
        to avoid treating content sub-headings (e.g. inside CHAT_WITH_USER) as actions.
        """
        headings: List[Heading] = []
        if doc.children is None:
            return headings

        valid_actions = {action.value for action in ActionType}

        children_list = list(doc.children)
        try:
            start_index = children_list.index(start_node)
            for child in children_list[start_index + 1 :]:
                if isinstance(child, Heading) and child.level == 3:
                    # Check if this heading is a valid action header
                    # Expected format: ### `ACTION_TYPE`
                    text = self._get_child_text(child).strip()
                    # A naive check: does the text (minus backticks) match a valid action?
                    # We look for the action type at the start of the string
                    # e.g. "`CREATE`" or "`CREATE`: some description"

                    # Extract the first token which should be the action type
                    # We handle the case where it might be wrapped in backticks
                    potential_type = text.split(":")[0].strip().replace("`", "")

                    if potential_type in valid_actions:
                        headings.append(child)
                    else:
                        # Include unknown actions if formatted as code (e.g., `UNKNOWN`)
                        # so they fail validation explicitly.
                        # mistletoe types .children as Iterable, but it's usually a list.
                        # We cast to list to safely index it.
                        children = list(child.children) if child.children else []
                        if children and isinstance(children[0], InlineCode):
                            headings.append(child)

                elif isinstance(child, Heading) and child.level <= 2:
                    break
        except ValueError:
            pass  # start_node not found
        return headings

    def _parse_create_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses a CREATE action block."""
        metadata_list = self._get_next_sibling(parent, heading_node)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("CREATE action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list, link_key_map={"File Path": "path"}
        )

        code_block = self._find_next_node_of_type(parent, metadata_list, CodeFence)
        if not code_block:
            raise InvalidPlanError("CREATE action is missing a content code block.")

        params["content"] = ""
        if code_block.children:
            children = list(code_block.children)
            if children:
                child = children[0]
                if hasattr(child, "content"):
                    # Use content directly to preserve trailing newlines, but strip the
                    # single trailing newline that mistletoe always includes.
                    params["content"] = child.content.rstrip("\n")

        return ActionData(type="CREATE", description=description, params=params)

    def _parse_resource_action(
        self, parent: Document, heading_node: Heading, action_type: str
    ) -> ActionData:
        """Parses a generic resource-based action block (e.g., READ, PRUNE)."""
        metadata_list = self._get_next_sibling(parent, heading_node)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError(f"{action_type} action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list, link_key_map={"Resource": "resource"}
        )

        if description:
            params["Description"] = description

        return ActionData(type=action_type, description=description, params=params)

    def _parse_read_action(self, parent: Document, heading_node: Heading) -> ActionData:
        """Parses a READ action block."""
        return self._parse_resource_action(parent, heading_node, "READ")

    def _parse_prune_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses a PRUNE action block."""
        return self._parse_resource_action(parent, heading_node, "PRUNE")

    def _parse_edit_action(self, parent: Document, heading_node: Heading) -> ActionData:
        """Parses an EDIT action block using a robust state machine."""
        metadata_list = self._get_next_sibling(parent, heading_node)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("EDIT action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list, link_key_map={"File Path": "path"}
        )

        content_nodes = self._get_subsequent_siblings(parent, metadata_list)
        edits = []

        # State machine variables
        state = "AWAITING_FIND_HEADING"
        current_find_content: Optional[str] = None

        if os.environ.get("TEDDY_DEBUG"):
            print("\n--- AST Node Trace for EDIT Action ---")
            for i, node in enumerate(content_nodes):
                print(f"Node {i}: {repr(node)}")
            print("--------------------------------------\n")

        for node in content_nodes:
            if state == "AWAITING_FIND_HEADING":
                if isinstance(node, Heading) and "FIND:" in self._get_child_text(node):
                    state = "AWAITING_FIND_CODE"
                continue

            if state == "AWAITING_FIND_CODE":
                if isinstance(node, (CodeFence, BlockCode)):
                    # Directly access the content of the code block's child RawText node
                    # to get the verbatim content, preserving any trailing newlines.
                    if node.children:
                        raw_text_node = list(node.children)[0]
                        current_find_content = getattr(
                            raw_text_node, "content", ""
                        ).rstrip("\n")
                    else:
                        current_find_content = ""
                    state = "AWAITING_REPLACE_HEADING"
                elif isinstance(node, Heading):
                    state = "AWAITING_FIND_HEADING"
                continue

            if state == "AWAITING_REPLACE_HEADING":
                if isinstance(node, Heading) and "REPLACE:" in self._get_child_text(
                    node
                ):
                    state = "AWAITING_REPLACE_CODE"
                continue

            if state == "AWAITING_REPLACE_CODE":
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
                    # Reset for the next potential FIND/REPLACE pair
                    state = "AWAITING_FIND_HEADING"
                    current_find_content = None
                # If we see another heading before a code block, it's malformed. Reset.
                elif isinstance(node, Heading):
                    state = "AWAITING_FIND_HEADING"
                continue

        if not edits:
            raise InvalidPlanError("EDIT action found no valid FIND/REPLACE blocks.")

        params["edits"] = edits
        return ActionData(type="EDIT", description=description, params=params)

    def _parse_return_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses a RETURN action block."""
        next_node = self._get_next_sibling(parent, heading_node)
        start_node = next_node if isinstance(next_node, MdList) else heading_node

        params = self._parse_message_and_optional_resources(parent, start_node)

        if "message" not in params:
            raise InvalidPlanError("RETURN action is missing message content.")

        return ActionData(type="RETURN", description=None, params=params)

    def _parse_message_and_optional_resources(
        self, parent: Document, start_node: Any
    ) -> dict[str, Any]:
        """
        Parses a block that contains optional Handoff Resources and a message body.
        `start_node` is the node from which to start searching for subsequent siblings
        that make up the message body. If `start_node` is a list, it will also be
        checked for Handoff Resources.
        """
        params: dict[str, Any] = {}
        content_nodes_start_node = start_node

        if isinstance(start_node, MdList):
            resources = []
            if start_node.children:
                for item in start_node.children:
                    item_text = self._get_child_text(item).strip()
                    if item_text.startswith("Handoff Resources:"):
                        resource_list = self._find_node_in_tree(item, MdList)
                        if resource_list and resource_list.children:
                            for res_item in resource_list.children:
                                link = self._find_node_in_tree(res_item, Link)
                                if link:
                                    target = link.target
                                    # Normalize path
                                    resources.append(
                                        self._normalize_link_target(target)
                                    )
            if resources:
                params["handoff_resources"] = resources

        content_nodes = self._get_subsequent_siblings(parent, content_nodes_start_node)

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

    def _parse_invoke_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses an INVOKE action block."""
        metadata_list = self._get_next_sibling(parent, heading_node)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("INVOKE action is missing metadata list.")

        _, params = self._parse_action_metadata(
            metadata_list, link_key_map={}, text_key_map={"Agent": "agent"}
        )

        message_params = self._parse_message_and_optional_resources(
            parent, metadata_list
        )
        params.update(message_params)

        if "message" not in params:
            raise InvalidPlanError("INVOKE action is missing message content.")

        return ActionData(type="INVOKE", description=None, params=params)

    def _parse_execute_action(self, doc: Document, heading: Heading) -> ActionData:
        """Parses an EXECUTE action block."""
        metadata_list = self._get_next_sibling(doc, heading)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("EXECUTE action is missing metadata list.")

        description, params = self._parse_action_metadata(
            metadata_list,
            link_key_map={},
            text_key_map={
                "Expected Outcome": "expected_outcome",
                "cwd": "cwd",
            },
        )

        # Env is nested and needs special handling
        env_dict: Dict[str, str] = {}
        if metadata_list.children:
            for item in metadata_list.children:
                item_text = self._get_child_text(item).strip()
                if item_text.startswith("env:"):
                    env_list = self._find_node_in_tree(item, MdList)
                    if env_list and env_list.children:
                        for env_item in env_list.children:
                            if isinstance(env_item, ListItem):
                                env_text = self._get_child_text(env_item).strip()
                                if ":" in env_text:
                                    key, value = [
                                        part.strip() for part in env_text.split(":", 1)
                                    ]
                                    env_dict[key] = value.strip('"')
        if env_dict:
            params["env"] = env_dict

        command_block = self._find_next_node_of_type(doc, metadata_list, CodeFence)
        if not command_block:
            raise InvalidPlanError("EXECUTE action is missing command code block.")

        params["command"] = self._get_child_text(command_block).strip()

        if description:
            params["Description"] = description

        return ActionData(type="EXECUTE", description=description, params=params)

    def _parse_research_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses a RESEARCH action block."""
        metadata_list = self._get_next_sibling(parent, heading_node)
        if not isinstance(metadata_list, MdList):
            raise InvalidPlanError("RESEARCH action is missing metadata list.")

        description, _ = self._parse_action_metadata(metadata_list, link_key_map={})

        content_nodes = self._get_subsequent_siblings(parent, metadata_list)
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

    def _parse_chat_with_user_action(
        self, parent: Document, heading_node: Heading
    ) -> ActionData:
        """Parses a CHAT_WITH_USER action block."""
        content_nodes = self._get_subsequent_siblings(parent, heading_node)

        if not content_nodes:
            raise InvalidPlanError("CHAT_WITH_USER action is missing prompt content.")

        # To correctly reconstruct the prompt while preserving formatting and
        # paragraph breaks, we must render each block-level node individually
        # and then join them with the appropriate separator.
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
            type="CHAT_WITH_USER",
            description=None,  # This action type has no description metadata
            params={"prompt": prompt},
        )

    def _parse_action_metadata(
        self,
        metadata_list: MdList,
        link_key_map: dict[str, str],
        text_key_map: Optional[dict[str, str]] = None,
    ) -> tuple[Optional[str], dict[str, Any]]:
        """
        Parses the common metadata list for an action.
        Extracts the description and any specified link-based parameters.
        """
        params: dict[str, Any] = {}
        description: Optional[str] = None
        if not metadata_list.children:
            return description, params

        for item in metadata_list.children:
            text = self._get_child_text(item)
            if "Description:" in text:
                description = text.split(":", 1)[1].strip()
                continue

            for key_text, param_key in link_key_map.items():
                if f"{key_text}:" in text:
                    link_node = self._find_node_in_tree(item, Link)
                    if link_node:
                        params[param_key] = self._normalize_link_target(
                            link_node.target
                        )
                    else:
                        # Fallback: Extract raw text value if no link node is found
                        parts = text.split(f"{key_text}:", 1)
                        if len(parts) == 2:
                            value = parts[1].strip()
                            if value:
                                params[param_key] = value
                    break
            else:  # If no link key matched, check for text keys
                if text_key_map:
                    for key_text, param_key in text_key_map.items():
                        if f"{key_text}:" in text:
                            params[param_key] = text.split(":", 1)[1].strip()
                            break
        return description, params

    # --- AST Helper Methods ---

    def _normalize_link_target(self, target: str) -> str:
        """
        Differentiates between a project-relative path (e.g., `[/docs/spec.md]`)
        and a true absolute path (e.g., `[/tmp/file.txt]`).

        - Strips the leading '/' from project-relative paths.
        - Preserves true absolute paths.
        - Handles URLs gracefully.
        """
        if target.startswith(("http://", "https://")):
            return target

        is_abs = os.path.isabs(target)
        is_likely_true_absolute = False

        if os.name == "nt":
            # On Windows, a "true" absolute path has a drive letter.
            # A path like "/file.txt" is absolute relative to the current drive,
            # but in our context, it should be treated as project-relative.
            has_drive, _ = os.path.splitdrive(target)
            if is_abs and has_drive:
                is_likely_true_absolute = True
        elif os.name == "posix" and is_abs:
            # On POSIX, use a heuristic of common system directories.
            common_roots = (
                "/bin",
                "/etc",
                "/home",
                "/lib",
                "/opt",
                "/private",
                "/proc",
                "/root",
                "/tmp",
                "/usr",
                "/var",
            )
            if target.startswith(common_roots):
                is_likely_true_absolute = True

        # We strip the leading slash only if it's a project-relative path
        # (i.e., it starts with '/' but is not a "true" absolute path).
        if target.startswith("/") and not is_likely_true_absolute:
            return target.lstrip("/")

        return target

    def _find_node_in_tree(self, node: Any, node_type: type) -> Optional[Any]:
        """Recursively searches for a node of a specific type in a tree."""
        if isinstance(node, node_type):
            return node
        if hasattr(node, "children") and node.children is not None:
            for child in node.children:
                found = self._find_node_in_tree(child, node_type)
                if found:
                    return found
        return None

    def _get_child_text(self, node: Any) -> str:
        """Recursively gets all text from a node's children."""
        if hasattr(node, "children") and node.children is not None:
            return "".join([self._get_child_text(child) for child in node.children])
        return getattr(node, "content", "")

    def _find_heading(
        self, doc: Document, text: str, level: int = 2
    ) -> Optional[Heading]:
        """Finds a heading with specific text and level."""
        if doc.children is None:
            return None
        for node in doc.children:
            if isinstance(node, Heading) and node.level == level:
                if text in self._get_child_text(node):
                    return node
        return None

    def _find_next_node_of_type(
        self, parent: Document, start_node: Any, node_type: type
    ) -> Optional[Any]:
        """Finds the next sibling node of a specific type."""
        if parent.children is None:
            return None
        children_list = list(parent.children)
        try:
            start_index = children_list.index(start_node)
            for node in children_list[start_index + 1 :]:
                if isinstance(node, node_type):
                    return node
                if isinstance(node, Heading) and node.level <= 3:
                    break
        except (ValueError, IndexError):
            return None
        return None

    def _get_next_sibling(self, parent: Document, node: Any) -> Optional[Any]:
        """Finds the immediate next sibling of a node."""
        if parent.children is None:
            return None
        children_list = list(parent.children)
        try:
            index = children_list.index(node)
            return children_list[index + 1]
        except (ValueError, IndexError):
            return None

    def _get_subsequent_siblings(self, parent: Document, start_node: Any) -> list[Any]:
        """
        Returns a list of all sibling nodes after start_node until a new Action
        (valid H3 action header) or a new Section (H1/H2) is encountered.
        """
        siblings: list[Any] = []
        if parent.children is None:
            return siblings

        valid_actions = {action.value for action in ActionType}

        children_list = list(parent.children)
        try:
            start_index = children_list.index(start_node)
            for node in children_list[start_index + 1 :]:
                if isinstance(node, Heading):
                    # Always break on H1 or H2 (Major Sections)
                    if node.level <= 2:
                        break

                    # For H3, check if it is a valid Action Header
                    if node.level == 3:
                        text = self._get_child_text(node).strip()
                        potential_type = text.split(":")[0].strip().replace("`", "")
                        if potential_type in valid_actions:
                            break
                        # If H3 but not a valid action, treat as content and continue loop.

                siblings.append(node)
        except (ValueError, IndexError):
            pass
        return siblings
