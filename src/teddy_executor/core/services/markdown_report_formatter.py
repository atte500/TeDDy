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

    _cached_env = None
    _cached_template = None

    @classmethod
    def _reset_singleton(cls):
        """Internal helper for test isolation."""
        cls._cached_env = None
        cls._cached_template = None

    def __init__(self):
        from jinja2 import Environment, FileSystemLoader

        if MarkdownReportFormatter._cached_env is None:
            template_dir = os.path.join(os.path.dirname(__file__), "templates")
            env = Environment(
                loader=FileSystemLoader(template_dir),
                trim_blocks=True,
                lstrip_blocks=True,
                autoescape=False,  # nosec B701
            )
            env.filters["basename"] = os.path.basename
            env.filters["fence"] = get_fence_for_content
            env.filters["language_from_path"] = get_language_from_path

            MarkdownReportFormatter._cached_env = env
            MarkdownReportFormatter._cached_template = env.get_template(
                "execution_report.md.j2"
            )

        self.env = MarkdownReportFormatter._cached_env
        self.template = MarkdownReportFormatter._cached_template

    def _prepare_context(self, report: ExecutionReport) -> dict[str, Any]:
        """Prepares the report data for rendering."""

        def format_datetime(dt):
            if not dt:
                return ""
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.isoformat()

        plan_title: str = "Untitled Plan"
        if hasattr(report, "plan_title"):
            val = getattr(report, "plan_title")
            plan_title = str(val) if val is not None else "Untitled Plan"
        elif isinstance(report, dict):
            plan_title = str(report.get("plan_title", "Untitled Plan"))

        is_session = False
        if hasattr(report, "is_session"):
            is_session = bool(getattr(report, "is_session"))
        elif isinstance(report, dict):
            is_session = bool(report.get("is_session", False))

        return {
            "report": report,
            "is_session": is_session,
            "plan_title": plan_title,
            "format_datetime": format_datetime,
        }

    def format(self, report: ExecutionReport) -> str:
        """Renders the execution report to a Markdown string."""
        from teddy_executor.core.utils.serialization import (
            scrub_dict_for_serialization,
        )

        # 1. Prepare context with real objects to support attribute access in Python
        context = self._prepare_context(report)

        # 2. Scrub the report data specifically to neutralize mocks for Jinja2
        report_data = (
            report.__dict__
            if hasattr(report, "__dict__")
            else (report if isinstance(report, dict) else {})
        )
        context["report"] = scrub_dict_for_serialization(report_data)

        # 3. Render with scrubbed data but real functions
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
