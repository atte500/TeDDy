"""Unit tests for SessionPruningService._check_report_has_user_request.

Covers the detection of user_request metadata in report files.
This method is the core of Slice 02-10 (Preserve User-Message Turns).
"""

from unittest.mock import create_autospec
import pytest
from teddy_executor.core.domain.models.project_context import (
    ContextItem,
    ProjectContext,
)
from teddy_executor.core.services.session_pruning_service import (
    SessionPruningService,
)
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager


@pytest.fixture
def service():
    """Create a SessionPruningService with mocked dependencies.

    Module-level fixture used by both TestCheckReportHasUserRequest
    and TestSparedTurnIntegration.
    """
    config_svc = create_autospec(IConfigService, instance=True)
    fs_mock = create_autospec(IFileSystemManager, instance=True)
    return SessionPruningService(
        config_service=config_svc,
        file_system_manager=fs_mock,
    )


class TestCheckReportHasUserRequest:
    """A helper method that detects the ``## User Request`` heading pattern in report files.

    The method reads a report file and checks for the pattern using regex.
    It returns True if the pattern is found, False if the file is missing,
    unreadable, or the pattern is absent.
    """

    def test_detects_user_request_header_in_report(self, service):
        """Positive: Report containing '## User Request' returns True."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n"
            "- **Overall Status:** SUCCESS\n"
            "\n"
            "## User Request\n"
            "```text\n"
            "Add new feature\n"
            "```\n"
        )

        # Act
        result = service._check_report_has_user_request("01/report.md")

        # Assert
        assert result is True

    def test_detects_user_request_header_without_content(self, service):
        """Positive: Report with empty user_request heading still returns True.

        The presence of the heading itself indicates user interaction occurred,
        even if the content is empty. The regex matches the heading line.
        """
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n- **Overall Status:** SUCCESS\n\n## User Request\n"
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

        The regex r"^## User Request" with re.MULTILINE matches
        the pattern wherever it appears on its own line. This is by design —
        the presence of the header itself indicates user interaction, regardless
        of code block context. In production, the report template renders this
        header as a Markdown heading on its own line.
        """
        # Arrange
        mock_fs = service._file_system_manager
        mock_fs.path_exists.return_value = True
        mock_fs.read_file.return_value = (
            "# Execution Report\n"
            "- **Overall Status:** SUCCESS\n"
            "```\n"
            "## User Request\n"
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


class TestSparedTurnIntegration:
    """Integration-level tests: turns with user_request are not pruned by heuristics.

    These tests exercise the full prune() pipeline through the pruning service,
    simulating a multi-turn session with controlled config settings.
    The user_request sparing logic in _update_turn_metadata_from_item is not
    yet implemented, so these tests are expected to FAIL (Red phase).
    """

    def _make_item(
        self,
        path: str,
        scope: str = "Turn",
        token_count: int = 1000,
        selected: bool = True,
        git_status: str = " ",
    ) -> ContextItem:
        return ContextItem(
            path=path,
            scope=scope,
            token_count=token_count,
            selected=selected,
            git_status=git_status,
        )

    def test_user_request_turn_not_pruned_by_retention_limit(self, service):
        """When retention limit is 1, the oldest turn (with user_request) should be spared.

        Setup: 3 turns (00, 01, 02). Retention limit = 1 means tid <= 1 are eligible.
        - Turn 00 (no user_request, tid=0): exceeded retention → PRUNED
        - Turn 01 (has user_request, tid=1): eligible but SPARED
        - Turn 02 (no user_request, tid=2): newest, in limit → STAYS
        """
        # Arrange
        mock_fs = service._file_system_manager
        mock_config = service._config_service

        # Config: retention limit = 1, preserve messages = True, no budget limit
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "auto_pruning.enabled": True,
            "auto_pruning.prune_failure_history": False,
            "auto_pruning.prune_validation_failures": False,
            "auto_pruning.preserve_message_turns": True,
            "auto_pruning.max_turns_retention": 1,
            "auto_pruning.turn_context_threshold": 0,
        }.get(key, default)

        # Mock files: turn 00 normal, turn 01 has user_request, turn 02 normal
        mock_fs.path_exists.return_value = True

        def read_file(path: str) -> str:
            _contents = {
                "00/report.md": "# Report\n- **Overall Status:** SUCCESS\n",
                "00/plan.md": "# Plan\n- **Status:** Green 🟢\n",
                "01/report.md": (
                    "# Report\n"
                    "- **Overall Status:** SUCCESS\n"
                    "\n"
                    "## User Request\n"
                    "```text\n"
                    "fix the bug\n"
                    "```\n"
                ),
                "01/plan.md": "# Plan\n- **Status:** Green 🟢\n",
                "02/report.md": "# Report\n- **Overall Status:** SUCCESS\n",
                "02/plan.md": "# Plan\n- **Status:** Green 🟢\n",
            }
            return next((v for k, v in _contents.items() if k in str(path)), "")

        mock_fs.read_file.side_effect = read_file

        # Build context: 3 turns, turn 01 has user_request
        items = [
            self._make_item(path=".teddy/sessions/test/00/report.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/00/plan.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/01/report.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/01/plan.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/02/report.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/02/plan.md", token_count=100),
        ]

        context = ProjectContext(items=items, header="", content="")

        # Act
        result = service.prune(context, current_status="🟢")

        # Assert helpers
        def get_item(path_substring: str):
            return next((i for i in result.items if path_substring in i.path), None)

        # Turn 00 (no user_request, tid=0) — exceeds retention limit → pruned
        turn00_report = get_item("00/report.md")
        turn00_plan = get_item("00/plan.md")
        assert turn00_report is not None
        assert turn00_report.selected is False, (
            "Turn 00 without sparing should be pruned by retention limit"
        )
        assert turn00_plan is not None
        assert turn00_plan.selected is False

        # Turn 01 (has user_request, tid=1) — eligible for pruning but spared
        turn01_report = get_item("01/report.md")
        turn01_plan = get_item("01/plan.md")
        assert turn01_report is not None
        assert turn01_report.selected is True, (
            "Turn with user_request should NOT be pruned by retention limit"
        )
        assert turn01_plan is not None
        assert turn01_plan.selected is True

        # Turn 02 (no user_request, tid=2) — newest turn, in retention limit → stays
        turn02_report = get_item("02/report.md")
        turn02_plan = get_item("02/plan.md")
        assert turn02_report is not None
        assert turn02_report.selected is True, (
            "Newest turn should not be pruned by retention limit"
        )
        assert turn02_plan is not None
        assert turn02_plan.selected is True

    def test_user_request_turn_not_pruned_by_global_budget(self, service):
        """When turn_context_threshold is low, the user_request turn should be spared."""
        # Arrange
        mock_fs = service._file_system_manager
        mock_config = service._config_service

        # Config: threshold = 100 (very low), preserve messages = True, no retention
        mock_config.get_setting.side_effect = lambda key, default=None: {
            "auto_pruning.enabled": True,
            "auto_pruning.prune_failure_history": False,
            "auto_pruning.prune_validation_failures": False,
            "auto_pruning.preserve_message_turns": True,
            "auto_pruning.max_turns_retention": 0,
            "auto_pruning.turn_context_threshold": 100,
        }.get(key, default)

        # Mock files: turn 01 has user_request report; turn 02 has normal report
        mock_fs.path_exists.return_value = True

        def read_file(path: str) -> str:
            if "01/report.md" in str(path):
                return (
                    "# Report\n"
                    "- **Overall Status:** SUCCESS\n"
                    "\n"
                    "## User Request\n"
                    "```text\n"
                    "add more tests\n"
                    "```\n"
                )
            if "01/plan.md" in str(path):
                return "# Plan\n- **Status:** Green 🟢\n"
            if "02/report.md" in str(path):
                return "# Report\n- **Status:** SUCCESS\n"
            if "02/plan.md" in str(path):
                return "# Plan\n- **Status:** Green 🟢\n"
            return ""

        mock_fs.read_file.side_effect = read_file

        # Build context: turn 01 has large token count (will exceed budget),
        # turn 02 has small token count.
        items = [
            self._make_item(path=".teddy/sessions/test/01/report.md", token_count=5000),
            self._make_item(path=".teddy/sessions/test/01/plan.md", token_count=5000),
            self._make_item(path=".teddy/sessions/test/02/report.md", token_count=100),
            self._make_item(path=".teddy/sessions/test/02/plan.md", token_count=100),
        ]

        context = ProjectContext(items=items, header="", content="")

        # Act
        result = service.prune(context, current_status="🟢")

        # Assert: turn 01 (user_request) must remain selected even though it's large
        turn01_report = next(
            (i for i in result.items if "01/report.md" in i.path), None
        )
        turn01_plan = next((i for i in result.items if "01/plan.md" in i.path), None)
        turn02_report = next(
            (i for i in result.items if "02/report.md" in i.path), None
        )
        turn02_plan = next((i for i in result.items if "02/plan.md" in i.path), None)

        assert turn01_report is not None
        assert turn01_report.selected is True, (
            "Turn with user_request should NOT be pruned by global budget"
        )
        assert turn01_plan is not None
        assert turn01_plan.selected is True

        # Turn 02 (no user_request) should be pruned (largest non-spared)
        assert turn02_report is not None
        assert turn02_report.selected is False, (
            "Turn without sparing should be pruned by global budget"
        )
        assert turn02_plan is not None
        assert turn02_plan.selected is False
