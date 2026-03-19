import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ActionLogEntry:
    """A structured representation of a single action's outcome in a report."""

    type: str
    status: str
    params: Dict[str, str] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


class ReportParser:
    """
    Observer in the Test Harness Triad.
    Parses Markdown Execution Reports back into structured data.
    """

    @property
    def stdout(self) -> str:
        """Returns the raw Markdown content of the report."""
        return self._content

    @property
    def summary(self) -> Dict[str, str]:
        """Returns the parsed summary fields."""
        return self.run_summary

    def __init__(self, content: str):
        self._content = content
        self.run_summary: Dict[str, str] = {}
        self.action_logs: List[ActionLogEntry] = []
        self._parse()

    def _parse(self):
        """Orchestrates the parsing of the report content."""
        # Use regex to split by H2 headings to isolate sections
        sections = re.split(r"(?m)^##\s+", self._content)

        # Section 0 is title and summary
        summary_text = sections[0]
        for line in summary_text.splitlines():
            match = re.match(r"-\s*\*\*(.+?):\*\*\s*(.*)", line)
            if match:
                key = match.group(1).strip()
                value = match.group(2).strip().strip("`").strip()
                self.run_summary[key] = value

        # Parse other sections
        self.resource_contents: Dict[str, str] = {}
        for section in sections[1:]:
            if section.startswith("Action Log"):
                self._parse_action_logs(section)
            elif section.startswith("Resource Contents"):
                self._parse_resource_contents(section)

    def _parse_action_logs(self, section: str):
        # Split by action headings (H3) - allow lowercase and different status styles
        chunks = re.split(r"(?m)(?=^\s*###\s*`)", section)
        for chunk in chunks:
            if entry := self._parse_action_chunk(chunk):
                self.action_logs.append(entry)

    def _parse_resource_contents(self, section: str):
        # Resource blocks are H3 links followed by code blocks
        # ### [basename](path)
        # ````[lang]
        # content
        # ````
        chunks = re.split(r"(?m)(?=^\s*###\s*\[)", section)
        for chunk in chunks:
            # Match the link destination if available, otherwise the text
            path_match = re.search(r"###\s*\[.*?\]\((.*?)\)", chunk)
            if not path_match:
                path_match = re.search(r"###\s*\[(.*?)\]", chunk)

            if path_match:
                path = path_match.group(1).lstrip("/")
                # Lenient content matching (allows optional language and varying newlines)
                content_match = re.search(
                    r"(`{3,})(?:\w+)?\s*\n(.*?)\n\s*\1", chunk, re.DOTALL
                )
                if content_match:
                    self.resource_contents[path] = content_match.group(2).strip()

    def extract_resource_contents(self) -> Dict[str, str]:
        """Returns the dictionary of resource contents found in the report."""
        return self.resource_contents

    def _parse_action_chunk(self, chunk: str) -> Optional[ActionLogEntry]:
        """Parses a single H3 action block."""
        chunk = chunk.strip()
        if not chunk:
            return None

        heading_match = re.search(r"###\s*`(\w+)`(?::\s*(.*))?", chunk)
        if not heading_match:
            return None

        action_type = heading_match.group(1).upper()
        subject = heading_match.group(2).strip() if heading_match.group(2) else None
        params, details = self._extract_params_and_details(action_type, subject, chunk)

        # Flexible status matching for various template versions
        status_match = re.search(
            r"-\s*\*\*Status:\*\*\s*(?:\n\s*-\s*)?([A-Z_]+)",
            chunk,
            re.IGNORECASE | re.MULTILINE,
        )
        status = status_match.group(1).upper() if status_match else "UNKNOWN"

        # Extract Skip Reason/Note/Details if present
        skip_match = re.search(
            r"-\s*\*\*(?:Skip Reason|Note|Details):\*\*\s*(?:`?)(.*?)(?:`?)$",
            chunk,
            re.MULTILINE,
        )
        if skip_match:
            params["Skip Reason"] = skip_match.group(1).strip()

        return ActionLogEntry(
            type=action_type, status=status, params=params, details=details
        )

    def _extract_params_and_details(
        self, action_type: str, subject: Optional[str], chunk: str
    ) -> Tuple[Dict, Dict]:
        """Extracts params and details from the chunk."""
        params: Dict[str, str] = {}
        if subject:
            self._apply_subject_to_params(action_type, subject, params)

        details: Dict[str, Any] = {}
        for line in chunk.splitlines():
            match = re.match(r"-\s*\*\*(.+?):\*\*\s*(.*)", line)
            if match:
                key, value = (
                    match.group(1).strip(),
                    match.group(2).strip().strip("`").strip(),
                )
                if key in ["Status", "Error", "Return Code", "Details"]:
                    if key == "Return Code" and value:
                        details["return_code"] = int(value)
                    if key == "Details":
                        details["details"] = value
                    continue
                params[key] = value

        self._extract_content_blocks(chunk, details)
        return params, details

    def _apply_subject_to_params(
        self, action_type: str, subject: str, params: Dict[str, str]
    ):
        """Maps the heading subject to the params dict based on action type."""
        # Strip Markdown links: [text](path) -> path
        link_match = re.search(r"\[.*?\]\((.*?)\)", subject)
        if link_match:
            subject = link_match.group(1).lstrip("/")

        if action_type in ["CREATE", "EDIT", "READ", "PRUNE"]:
            params["File Path"] = subject
            if action_type == "READ":
                params["Resource"] = subject
        elif action_type in ["EXECUTE", "RESEARCH", "PROMPT", "INVOKE", "RETURN"]:
            params["Description"] = subject.strip('"').strip("'")

    def _extract_content_blocks(self, chunk: str, details: Dict[str, Any]):
        """Extracts stdout/stderr/response blocks."""
        for block in ["stdout", "stderr", "User Response"]:
            block_match = re.search(
                rf"#### `?{block}`?\s*(`{{3,}})text\n(.*?)\n\1", chunk, re.DOTALL
            )
            if block_match:
                key = "response" if block == "User Response" else block
                details[key] = block_match.group(2).strip()

    def action_was_successful(self, index: int) -> bool:
        """Returns True if the action at the given index was successful."""
        if 0 <= index < len(self.action_logs):
            return self.action_logs[index].status == "SUCCESS"
        return False
