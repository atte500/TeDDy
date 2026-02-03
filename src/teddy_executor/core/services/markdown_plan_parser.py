from typing import Any, List, Optional
import mistletoe
from mistletoe.block_token import CodeFence, Heading, List as MdList, Document
from mistletoe.span_token import Link

from teddy_executor.core.domain.models import ActionData, Plan
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

        actions = self._parse_actions(doc)
        return Plan(actions=actions)

    def _parse_actions(self, doc: Document) -> List[ActionData]:
        """Finds and parses all action blocks within the 'Action Plan' section."""
        actions: List[ActionData] = []
        action_plan_heading = self._find_heading(doc, "Action Plan")
        if not action_plan_heading:
            raise InvalidPlanError("Plan is missing '## Action Plan' heading.")

        action_headings = self._find_action_headings(doc, action_plan_heading)

        for heading in action_headings:
            action_type = self._get_child_text(heading).strip().replace("`", "")
            if action_type == "CREATE":
                actions.append(self._parse_create_action(doc, heading))
            # Other action parsers will be added here

        if not actions:
            raise InvalidPlanError("No actions found in the 'Action Plan' section.")

        return actions

    def _find_action_headings(
        self, doc: Document, start_node: Heading
    ) -> List[Heading]:
        """Finds all H3 headings that represent actions."""
        headings: List[Heading] = []
        if doc.children is None:
            return headings
        children_list = list(doc.children)
        try:
            start_index = children_list.index(start_node)
            for child in children_list[start_index + 1 :]:
                if isinstance(child, Heading) and child.level == 3:
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

        params = {}
        description = None
        if metadata_list.children:
            for item in metadata_list.children:
                text = self._get_child_text(item)
                item_children = list(item.children) if item.children else []
                if "File Path:" in text and item_children:
                    first_child_children = (
                        list(item_children[0].children)
                        if item_children[0].children
                        else []
                    )
                    if first_child_children:
                        link_node = first_child_children[-1]
                        if isinstance(link_node, Link):
                            params["path"] = link_node.target
                elif "Description:" in text:
                    description = text.split(":", 1)[1].strip()

        code_block = self._find_next_node_of_type(parent, metadata_list, CodeFence)
        if not code_block:
            raise InvalidPlanError("CREATE action is missing a content code block.")

        if code_block.children:
            params["content"] = code_block.children[0].content.strip()
        else:
            params["content"] = ""

        return ActionData(type="CREATE", description=description, params=params)

    # --- AST Helper Methods ---

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
