import os
from datetime import timezone
from typing import Any

from jinja2 import Environment, FileSystemLoader

from teddy_executor.core.domain.models import ExecutionReport
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)


class MarkdownReportFormatter(IMarkdownReportFormatter):
    """
    Implements IMarkdownReportFormatter using the Jinja2 template engine.
    """

    def __init__(self):
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True)
        self.env.filters["basename"] = os.path.basename
        self.template = self.env.get_template("concise_report.md.j2")

    def _prepare_context(self, report: ExecutionReport) -> dict[str, Any]:
        """Prepares the report data for rendering."""

        import json

        def format_datetime(dt):
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        def to_json(obj):
            return json.dumps(obj, default=str)

        return {
            "report": report,
            "plan_title": report.plan_title,
            "format_datetime": format_datetime,
            "to_json": to_json,
        }

    def format(self, report: ExecutionReport) -> str:
        """Renders the execution report to a Markdown string."""
        context = self._prepare_context(report)
        return self.template.render(context)
