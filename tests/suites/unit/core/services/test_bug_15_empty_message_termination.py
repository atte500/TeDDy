"""Regression test for Bug #15: Empty message termination not triggered on communication turn reply."""

from unittest.mock import MagicMock
import punq

from teddy_executor.core.domain.models import (
    ActionData,
    ActionLog,
    ActionStatus,
    ExecutionReport,
    Plan,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import ISessionManager
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner


def _make_communication_plan(metadata: dict | None = None) -> Plan:
    """Create a minimal Plan that reports is_communication_turn() == True."""
    import types

    plan = Plan(
        title="Test Communication Turn",
        rationale="test",
        actions=[
            MagicMock(spec=ActionData, type="MESSAGE", params={}, description="Test")
        ],
        metadata=metadata or {"Agent": "test"},
        is_session=True,
    )
    # Override is_communication_turn to return True
    plan.is_communication_turn = types.MethodType(lambda self: True, plan)
    return plan


def _make_empty_reply_report() -> ExecutionReport:
    """Create an execution report with a MESSAGE ActionLog with empty details (simulating empty reply)."""
    from datetime import datetime

    return ExecutionReport(
        run_summary=RunSummary(
            status=RunStatus.SUCCESS,
            start_time=datetime.now(),
            end_time=datetime.now(),
        ),
        plan_title="Test",
        rationale="test",
        user_request=None,
        metadata={},
        is_session=True,
        original_actions=[],
        action_logs=[
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="MESSAGE",
                params={},
                details="",
            )
        ],
    )


class TestBug15EmptyMessageTermination:
    """Bug #15: Session must terminate without report.md when user provides empty reply to a Message turn."""

    def test_communication_turn_empty_reply_terminates_session(self):
        """Regression test: empty user_request after communication turn -> return None, no report.md."""
        container = punq.Container()
        fs_mock = MagicMock(spec=IFileSystemManager)
        exec_orch = MagicMock(spec=IRunPlanUseCase)
        session_svc = MagicMock(spec=ISessionManager)
        validator = MagicMock(spec=IPlanValidator)
        parser = MagicMock(spec=IPlanParser)
        interactor = MagicMock(spec=IUserInteractor)
        lifecycle_mgr = MagicMock(spec=SessionLifecycleManager)
        replanner = MagicMock(spec=SessionReplanner)
        context_svc = MagicMock(spec=IGetContextUseCase)
        config_svc = MagicMock(spec=IConfigService)
        llm_client = MagicMock(spec=ILlmClient)
        prompt_mgr = MagicMock(spec=IPromptManager)

        # Wire mocks
        fs_mock.path_exists.return_value = True  # meta.yaml exists -> is_session=True
        validator.validate.return_value = []  # No validation errors
        plan = _make_communication_plan()
        parser.parse.return_value = plan
        exec_orch.execute.return_value = _make_empty_reply_report()

        orchestrator = SessionOrchestrator(
            execution_orchestrator=exec_orch,
            session_service=session_svc,
            file_system_manager=fs_mock,
            plan_validator=validator,
            plan_parser=parser,
            user_interactor=interactor,
            lifecycle_manager=lifecycle_mgr,
            replanner=replanner,
            context_service=context_svc,
            config_service=config_svc,
            llm_client=llm_client,
            prompt_manager=prompt_mgr,
            pruning_service=None,
        )

        result = orchestrator.execute(
            plan_path=".teddy/sessions/test/01/plan.md",
            interactive=False,
        )

        # Assert: session terminates (None)
        assert result is None, (
            "Empty reply after communication turn should return None (terminate)"
        )

        # Assert: finalize_turn was NOT called (no report.md created)
        assert lifecycle_mgr.finalize_turn.call_count == 0, (
            "finalize_turn should NOT be called when terminating on empty reply"
        )

    def test_communication_turn_non_empty_reply_continues_session(self):
        """Non-empty user_request after communication turn should NOT terminate."""
        container = punq.Container()
        fs_mock = MagicMock(spec=IFileSystemManager)
        exec_orch = MagicMock(spec=IRunPlanUseCase)
        session_svc = MagicMock(spec=ISessionManager)
        validator = MagicMock(spec=IPlanValidator)
        parser = MagicMock(spec=IPlanParser)
        interactor = MagicMock(spec=IUserInteractor)
        lifecycle_mgr = MagicMock(spec=SessionLifecycleManager)
        replanner = MagicMock(spec=SessionReplanner)
        context_svc = MagicMock(spec=IGetContextUseCase)
        config_svc = MagicMock(spec=IConfigService)
        llm_client = MagicMock(spec=ILlmClient)
        prompt_mgr = MagicMock(spec=IPromptManager)

        fs_mock.path_exists.return_value = True
        validator.validate.return_value = []
        plan = _make_communication_plan()
        parser.parse.return_value = plan
        from datetime import datetime

        non_empty_report = ExecutionReport(
            run_summary=RunSummary(
                status=RunStatus.SUCCESS,
                start_time=datetime.now(),
                end_time=datetime.now(),
            ),
            plan_title="Test",
            rationale="test",
            user_request=None,
            metadata={},
            is_session=True,
            original_actions=[],
            action_logs=[
                ActionLog(
                    status=ActionStatus.SUCCESS,
                    action_type="MESSAGE",
                    params={},
                    details="Let's continue",
                )
            ],
        )
        exec_orch.execute.return_value = non_empty_report
        # Stub finalize_turn to return a path
        lifecycle_mgr.finalize_turn.return_value = ".teddy/sessions/test/02"

        orchestrator = SessionOrchestrator(
            execution_orchestrator=exec_orch,
            session_service=session_svc,
            file_system_manager=fs_mock,
            plan_validator=validator,
            plan_parser=parser,
            user_interactor=interactor,
            lifecycle_manager=lifecycle_mgr,
            replanner=replanner,
            context_service=context_svc,
            config_service=config_svc,
            llm_client=llm_client,
            prompt_manager=prompt_mgr,
            pruning_service=None,
        )

        result = orchestrator.execute(
            plan_path=".teddy/sessions/test/01/plan.md",
            interactive=False,
        )

        # Assert: session continues (non-None)
        assert result is not None, "Non-empty reply should NOT terminate session"

        # Assert: finalize_turn WAS called
        assert lifecycle_mgr.finalize_turn.call_count == 1, (
            "finalize_turn should be called when session continues"
        )
