"""Regression test for Bug 19: Execution failure context auto-add.

When an EDIT action fails at runtime (e.g., FIND block mismatch),
the action_logs entry has FAILURE status. The fix ensures that
_apply_execution_effects still adds the file path to the context set.
"""

import pytest
from unittest.mock import create_autospec
from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
    ActionStatus,
    ActionLog,
)
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.services.session_service import SessionService
from datetime import datetime


@pytest.fixture
def session_service():
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )
    from teddy_executor.core.ports.outbound.session_repository import ISessionRepository
    from teddy_executor.core.ports.outbound.time_service import ITimeService
    from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
    from teddy_executor.core.ports.inbound.init import IInitUseCase

    fs = create_autospec(IFileSystemManager)
    repo = create_autospec(ISessionRepository)
    time_svc = create_autospec(ITimeService)
    prompt_mgr = create_autospec(IPromptManager)
    init_svc = create_autospec(IInitUseCase)
    repo.is_valid_path.return_value = True
    return SessionService(
        file_system_manager=fs,
        repository=repo,
        time_service=time_svc,
        prompt_manager=prompt_mgr,
        init_service=init_svc,
    )


def make_report_with_action_logs(action_logs, original_actions=None):
    summary = RunSummary(
        status=RunStatus.FAILURE, start_time=datetime.now(), end_time=datetime.now()
    )
    return ExecutionReport(
        run_summary=summary,
        plan_title="Test Bug 19",
        action_logs=action_logs,
        original_actions=original_actions or [],
    )


class TestBug19ExecutionFailureContext:
    """Regression tests for Bug 19: file path auto-add on execution failure."""

    def test_path_added_when_edit_fails_at_runtime(self, session_service):
        """Execution failure with FAILURE status should still add the file path."""
        action_logs = [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type=ActionType.EDIT.value,
                params={"File Path": "src/some_file.py"},
                details="FIND block mismatch at runtime",
            ),
        ]
        report = make_report_with_action_logs(action_logs)
        paths = set()
        session_service._apply_execution_effects(paths, report)
        assert "src/some_file.py" in paths, (
            "FAILURE-status EDIT should add its file path to context"
        )

    def test_path_not_added_when_create_fails_at_runtime(self, session_service):
        """Execution failure for CREATE should NOT add the file path (per current spec)."""
        action_logs = [
            ActionLog(
                status=ActionStatus.FAILURE,
                action_type=ActionType.CREATE.value,
                params={"File Path": "src/new_file.py"},
                details="Write permission denied",
            ),
        ]
        report = make_report_with_action_logs(action_logs)
        paths = set()
        session_service._apply_execution_effects(paths, report)
        assert "src/new_file.py" not in paths

    def test_path_not_added_for_skipped_actions(self, session_service):
        """SKIPPED actions should NOT add their file paths."""
        action_logs = [
            ActionLog(
                status=ActionStatus.SKIPPED,
                action_type=ActionType.EDIT.value,
                params={"File Path": "src/skipped_file.py"},
            ),
        ]
        report = make_report_with_action_logs(action_logs)
        paths = set()
        session_service._apply_execution_effects(paths, report)
        assert "src/skipped_file.py" not in paths

    def test_path_not_added_for_pending_actions(self, session_service):
        """PENDING actions should NOT add their file paths."""
        action_logs = [
            ActionLog(
                status=ActionStatus.PENDING,
                action_type=ActionType.EDIT.value,
                params={"File Path": "src/pending_file.py"},
            ),
        ]
        report = make_report_with_action_logs(action_logs)
        paths = set()
        session_service._apply_execution_effects(paths, report)
        assert "src/pending_file.py" not in paths

    def test_path_added_for_success_actions(self, session_service):
        """Baseline: SUCCESS actions should continue to add their file paths."""
        action_logs = [
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type=ActionType.EDIT.value,
                params={"File Path": "src/success_file.py"},
            ),
        ]
        report = make_report_with_action_logs(action_logs)
        paths = set()
        session_service._apply_execution_effects(paths, report)
        assert "src/success_file.py" in paths
