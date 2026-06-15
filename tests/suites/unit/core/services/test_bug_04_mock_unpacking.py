"""Regression test for Bug #04: test mock missing get_session_state return value.

This test verifies that the production code raises a clear ValueError when
the session_service port's get_session_state method does not return a valid
tuple. This protects against mock poisoning in tests that exercise
_handle_planning_and_execution.
"""

from unittest.mock import MagicMock

import pytest

from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)


class TestMockUnpackingSafety:
    """Ensures _handle_planning_and_execution fails properly when get_session_state is missing."""

    def test_unconfigured_session_service_raises_value_error(self):
        """When session_service.get_session_state returns an empty MagicMock, ValueError must be raised."""
        ports = MagicMock()
        ports.file_system_manager = MagicMock()
        ports.report_formatter = MagicMock()
        ports.user_interactor = MagicMock()
        ports.session_planner = MagicMock()
        ports.session_planner.trigger_new_plan.return_value = "test"
        ports.replanner = MagicMock()
        ports.session_service = MagicMock()  # No return_value for get_session_state

        lifecycle = SessionLifecycleManager(ports)

        mock_orchestrator = MagicMock(spec=IRunPlanUseCase)
        mock_orchestrator.execute.return_value = MagicMock(run_summary=MagicMock())

        with pytest.raises(ValueError, match="not enough values to unpack"):
            lifecycle._handle_planning_and_execution(
                turn_dir="/root/session/turns/02",
                orchestrator=mock_orchestrator,
                interactive=False,
            )
