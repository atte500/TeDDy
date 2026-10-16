"""
This module defines the outbound port for markdown report formatting.
"""

from abc import ABC, abstractmethod


from teddy_executor.core.domain.models.execution_report import ExecutionReport


class IMarkdownReportFormatter(ABC):
    """
    Defines the contract for any service that can format an ExecutionReport
    into a final, user-facing Markdown string.
    """

    @abstractmethod
    def format(self, report: ExecutionReport) -> str:
        """
        Formats the report into a Markdown string.
        """
        raise NotImplementedError
