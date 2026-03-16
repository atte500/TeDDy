import os
from datetime import timezone
from typing import Any

from teddy_executor.core.domain.models import ExecutionReport
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)
from teddy_executor.core.utils.markdown import (
    get_fence_for_content,
    get_language_from_path,
)


class MarkdownReportFormatter(IMarkdownReportFormatter):
    """
    Implements IMarkdownReportFormatter using the Jinja2 template engine.
    """

    def __init__(self):
        from jinja2 import Environment, FileSystemLoader

        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # nosec B701
        )
        self.env.filters["basename"] = os.path.basename
        self.env.filters["fence"] = get_fence_for_content
        self.env.filters["language_from_path"] = get_language_from_path
        self.template = self.env.get_template("execution_report.md.j2")

    def _prepare_context(
        self, report: ExecutionReport, is_concise: bool
    ) -> dict[str, Any]:
        """Prepares the report data for rendering."""

        def format_datetime(dt):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        return {
            "report": report,
            "is_concise": is_concise,
            "plan_title": report.plan_title,
            "format_datetime": format_datetime,
        }

    def format(self, report: ExecutionReport, is_concise: bool = True) -> str:
        """Renders the execution report to a Markdown string."""
        context = self._prepare_context(report, is_concise)
        rendered = self.template.render(context)

        # Post-process for whitespace sanitization
        lines = [line.rstrip() for line in rendered.splitlines()]

        sanitized_lines = []
        in_fence = False
        consecutive_blanks = 0

        for line in lines:
            # Track code block state
            if line.strip().startswith("```"):
                in_fence = not in_fence

            if in_fence:
                # Inside code block: preserve all whitespace and newlines
                sanitized_lines.append(line)
                consecutive_blanks = 0
            # Outside code block: apply sanitization rules
            elif not line:
                consecutive_blanks += 1
                # Only allow one consecutive blank line (max 2 newlines)
                if consecutive_blanks <= 1:
                    sanitized_lines.append(line)
            else:
                consecutive_blanks = 0
                sanitized_lines.append(line)

        sanitized = "\n".join(sanitized_lines).strip()
        return sanitized
