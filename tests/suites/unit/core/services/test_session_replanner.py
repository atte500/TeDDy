"""Unit tests for SessionReplanner."""

import pytest

from teddy_executor.core.services.session_replanner import SessionReplanner


class DummyFileSystemManager:
    """Test double for file system manager that returns no resources."""

    def path_exists(self, path: str) -> bool:
        return False

    def read_file(self, path: str) -> str:
        return ""


class DummyPlanningService:
    """Test double for planning service that does nothing."""

    def generate_plan(self, user_message: str, turn_dir: str) -> None:
        pass


@pytest.fixture
def replanner() -> SessionReplanner:
    return SessionReplanner(
        file_system_manager=DummyFileSystemManager(),
        planning_service=DummyPlanningService(),
    )


class TestBuildFailureReportIsSession:
    """Tests for the is_session parameter forwarding in build_failure_report."""

    def test_default_is_session_false(self, replanner: SessionReplanner) -> None:
        """When is_session is not provided, it must default to False."""
        report = replanner.build_failure_report(
            errors=["Error 1"],
            title="Test Title",
            rationale="Test rationale",
            failed_resources={},
        )
        assert report.is_session is False

    @pytest.mark.parametrize("is_session", [True, False])
    def test_is_session_forwarded(
        self, replanner: SessionReplanner, is_session: bool
    ) -> None:
        """is_session must be forwarded to the ExecutionReport."""
        report = replanner.build_failure_report(
            errors=["Error 1"],
            title="Test Title",
            rationale="Test rationale",
            failed_resources={},
            is_session=is_session,
        )
        assert report.is_session == is_session
