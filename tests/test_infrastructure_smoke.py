from unittest.mock import Mock
from teddy_executor.core.services.edit_simulator import EditSimulator
from teddy_executor.core.ports.outbound.environment_inspector import (
    IEnvironmentInspector,
)
from teddy_executor.core.ports.outbound.markdown_report_formatter import (
    IMarkdownReportFormatter,
)


def test_can_resolve_edit_simulator(container, mock_edit_simulator):
    resolved = container.resolve(EditSimulator)
    assert resolved == mock_edit_simulator
    assert isinstance(resolved, Mock)


def test_can_resolve_inspector(container, mock_inspector):
    resolved = container.resolve(IEnvironmentInspector)
    assert resolved == mock_inspector
    assert isinstance(resolved, Mock)


def test_can_resolve_report_formatter(container, mock_report_formatter):
    resolved = container.resolve(IMarkdownReportFormatter)
    assert resolved == mock_report_formatter
    assert isinstance(resolved, Mock)
