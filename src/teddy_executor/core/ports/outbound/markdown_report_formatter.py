"""
This module defines the outbound port for markdown report formatting.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/ports/outbound/markdown_report_formatter.md

from abc import ABC, abstractmethod


from teddy_executor.core.domain.models.execution_report import ExecutionReport


class IMarkdownReportFormatter(ABC):
    """
    Defines the contract for any service that can format an ExecutionReport
    into a final, user-facing Markdown string.
    """

    @abstractmethod
    def format(self, report: ExecutionReport, is_concise: bool = True) -> str:
        """
        Formats the report into a Markdown string.
        """
        raise NotImplementedError
