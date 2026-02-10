"""
This module defines the outbound port for markdown report formatting.
"""

# Placeholder content
# The Developer will implement this based on the design document.
# See: docs/core/ports/outbound/markdown_report_formatter.md

from abc import ABC, abstractmethod


class IMarkdownReportFormatter(ABC):
    """
    Defines the contract for any service that can format an ExecutionReport
    into a final, user-facing Markdown string.
    """

    @abstractmethod
    def format(self, report) -> str:
        """
        Formats the report into a Markdown string.
        """
        raise NotImplementedError
