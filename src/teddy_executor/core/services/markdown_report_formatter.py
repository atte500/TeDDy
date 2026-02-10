"""
This module contains the implementation of the MarkdownReportFormatter service.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/services/markdown_report_formatter.md

from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)


class MarkdownReportFormatter(IMarkdownReportFormatter):
    """
    Implements IMarkdownReportFormatter using the Jinja2 template engine.
    """

    def format(self, report) -> str:
        # The Developer will implement the Jinja2 rendering logic here.
        return "# Execution Report: NOT IMPLEMENTED"
