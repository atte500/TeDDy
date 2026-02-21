import os
from datetime import timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader

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
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(
            loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True
        )
        self.env.filters["basename"] = os.path.basename
        self.env.filters["fence"] = get_fence_for_content
        self.env.filters["language_from_path"] = get_language_from_path
        self.template = self.env.get_template("concise_report.md.j2")

    def _prepare_context(self, report: ExecutionReport) -> dict[str, Any]:
        """Prepares the report data for rendering."""

        def format_datetime(dt):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        return {
            "report": report,
            "plan_title": report.plan_title,
            "format_datetime": format_datetime,
        }

    def format(self, report: ExecutionReport) -> str:
        """Renders the execution report to a Markdown string."""
        context = self._prepare_context(report)
        return self.template.render(context)
