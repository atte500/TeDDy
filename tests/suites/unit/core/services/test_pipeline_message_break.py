"""Regression test: Pipeline mode MESSAGE break guard.

Verifies that ActionExecutor.confirm_and_dispatch() with pipeline=True
short-circuits MESSAGE actions (produces synthetic ActionLog, no ask_question)
while pipeline=False (YOLO mode) dispatches normally.
"""

from unittest.mock import Mock
import pytest

from teddy_executor.core.domain.models import (
    ActionData,
    ActionStatus,
)
from teddy_executor.core.domain.models.action_ports import ActionPorts
from teddy_executor.core.ports.outbound import (
    IFileSystemManager,
    IShellExecutor,
    IUserInteractor,
    IConfigService,
    IWebScraper,
    IWebSearcher,
)
from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator
from teddy_executor.core.services.action_dispatcher import ActionDispatcher
from teddy_executor.core.services.action_factory import ActionFactory
from teddy_executor.core.services.action_executor import ActionExecutor


@pytest.fixture
def action_executor():
    """Build an ActionExecutor with mocked dependencies."""
    mock_fs = Mock(spec=IFileSystemManager)
    mock_shell = Mock(spec=IShellExecutor)
    mock_interactor = Mock(spec=IUserInteractor)
    mock_interactor.confirm_action.return_value = (True, "")
    mock_interactor.ask_question.return_value = "user reply"
    mock_web_scraper = Mock(spec=IWebScraper)
    mock_web_searcher = Mock(spec=IWebSearcher)
    mock_config = Mock(spec=IConfigService)
    mock_config.get_setting.return_value = None
    mock_config.get_config_path.return_value = ".teddy/config.yaml"
    mock_edit_simulator = Mock(spec=IEditSimulator)

    action_ports = ActionPorts(
        shell_executor=mock_shell,
        file_system_manager=mock_fs,
        user_interactor=mock_interactor,
        web_scraper=mock_web_scraper,
        web_searcher=mock_web_searcher,
        config_service=mock_config,
    )
    action_factory = ActionFactory(ports=action_ports)
    action_dispatcher = ActionDispatcher(action_factory=action_factory)
    executor = ActionExecutor(
        action_dispatcher=action_dispatcher,
        user_interactor=mock_interactor,
        file_system_manager=mock_fs,
        edit_simulator=mock_edit_simulator,
        config_service=mock_config,
    )
    return executor, mock_interactor


class TestPipelineMessageBreak:
    """Tests for pipeline MESSAGE guard in ActionExecutor.confirm_and_dispatch()."""

    def test_pipeline_mode_short_circuits_message(self, action_executor):
        """With pipeline=True and interactive=False, MESSAGE should produce
        synthetic ActionLog and NOT call ask_question."""
        executor, mock_interactor = action_executor
        action = ActionData(
            type="MESSAGE",
            params={"content": "Hello from pipeline!"},
            description="Say hello",
        )

        action_log, captured = executor.confirm_and_dispatch(
            action,
            interactive=False,
            total_actions=1,
            pipeline=True,
        )

        # Verify synthetic ActionLog
        assert action_log.action_type == "MESSAGE"
        assert action_log.status == ActionStatus.SUCCESS
        assert action_log.details == "Hello from pipeline!"

        # Verify ask_question was NOT called
        mock_interactor.ask_question.assert_not_called()

        # Verify captured message is empty (no user input needed)
        assert captured == ""

    def test_yolo_mode_dispatches_message(self, action_executor):
        """With pipeline=False and interactive=False (YOLO), MESSAGE should
        dispatch normally and call ask_question."""
        executor, mock_interactor = action_executor
        action = ActionData(
            type="MESSAGE",
            params={"content": "YOLO message"},
            description="YOLO test",
        )

        action_log, captured = executor.confirm_and_dispatch(
            action,
            interactive=False,
            total_actions=1,
            pipeline=False,
        )

        # Verify ActionLog is from dispatch (not synthetic)
        assert action_log.action_type == "MESSAGE"
        assert action_log.status == ActionStatus.SUCCESS
        # ask_question returns "user reply" -> that becomes details
        assert action_log.details == "user reply"

        # Verify ask_question WAS called
        mock_interactor.ask_question.assert_called_once()

    def test_pipeline_defaults_to_false(self, action_executor):
        """Existing callers without pipeline argument should work unchanged."""
        executor, mock_interactor = action_executor
        action = ActionData(
            type="MESSAGE",
            params={"content": "Default call"},
            description="Default",
        )

        # Call without pipeline argument -> defaults to False
        action_log, captured = executor.confirm_and_dispatch(
            action,
            interactive=False,
            total_actions=1,
        )

        # Should dispatch normally (ask_question is called)
        mock_interactor.ask_question.assert_called_once()
        assert action_log.status == ActionStatus.SUCCESS
        assert action_log.action_type == "MESSAGE"
        assert action_log.details == "user reply"
