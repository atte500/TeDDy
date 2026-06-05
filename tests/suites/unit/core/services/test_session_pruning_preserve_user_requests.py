"""Unit tests for SessionPruningService._check_report_has_user_request.

Covers the detection of user_request metadata in report files.
This method is the core of Slice 02-10 (Preserve User-Message Turns).
"""

from unittest.mock import create_autospec
import pytest
from teddy_executor.core.services.session_pruning_service import (
    SessionPruningService,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


class TestCheckReportHasUserRequest:
    """A helper method that detects the ``- **User Request:**`` pattern in report files.

    The method reads a report file and checks for the pattern using regex.
    It returns True if the pattern is found, False if the file is missing,
    unreadable, or the pattern is absent.
    """

    @pytest.fixture
    def service(self):
        """Create a SessionPruningService with mocked dependencies."""
        config_svc = create_autospec(IConfigService, instance=True)
        fs_mock = create_autospec(IFileSystemManager, instance=True)
        return SessionPruningService(
            config_service=config_svc,
            file_system_manager=fs_mock,
        )

    def test_detects_user_request_header_in_report(self, service):
        """Positive: Report containing '- **User Request:**' returns True."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n"
            "- **Overall Status:** SUCCESS\n"
            "- **User Request:** Add new feature\n"
        )

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is True

    def test_detects_user_request_header_without_content(self, service):
        """Positive: Report with empty user_request header still returns True.

        The presence of the key itself indicates user interaction occurred,
        even if the value is empty. The regex matches the line, not the value.
        """
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n- **Overall Status:** SUCCESS\n- **User Request:**\n"
        )

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is True

    def test_returns_false_when_no_user_request(self, service):
        """Negative: Report without user_request metadata returns False."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n- **Overall Status:** SUCCESS\n"
        )

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is False

    def test_returns_false_for_missing_report_file(self, service):
        """Edge: Missing report file returns False gracefully (no crash)."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = False

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is False

    def test_returns_false_for_unreadable_report_file(self, service):
        """Edge: When read_file raises, returns False gracefully."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.side_effect = FileNotFoundError("File not found")

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is False

    def test_matches_user_request_header_inside_code_block(self, service):
        r"""Positive: Pattern inside a code block still matches.

        The regex r"^- \*\*User Request:\*\*" with re.MULTILINE matches
        the pattern wherever it appears on its own line. This is by design —
        the presence of the header itself indicates user interaction, regardless
        of code block context. In production, the report template renders this
        header on its own metadata line.
        """
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n"
            "- **Overall Status:** SUCCESS\n"
            "```\n"
            "- **User Request:** inside code block\n"
            "```\n"
        )

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is True

    def test_returns_false_when_read_file_returns_empty_string(self, service):
        """Edge: Empty file returns False (no pattern to match)."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = ""

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is False
