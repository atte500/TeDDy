import punq
from tests.harness.setup.mocking import register_mock
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


class TestEmptyMessageTermination:
    """
    SessionOrchestrator must terminate without report.md when message is empty.
    """

    def test_empty_message_terminates_without_report(self):
        """Empty message (whitespace-only) -> return None, NO report.md written."""
        container = punq.Container()
        fs_mock = register_mock(container, IFileSystemManager)
        exec_orch = register_mock(container, IRunPlanUseCase)
        session_svc = register_mock(container, ISessionManager)
        validator = register_mock(container, IPlanValidator)
        parser = register_mock(container, IPlanParser)
        interactor = register_mock(container, IUserInteractor)
        lifecycle_mgr = register_mock(container, SessionLifecycleManager)
        replanner = register_mock(container, SessionReplanner)
        context_svc = register_mock(container, IGetContextUseCase)
        config_svc = register_mock(container, IConfigService)
        llm_client = register_mock(container, ILlmClient)
        prompt_mgr = register_mock(container, IPromptManager)

        # Stub validation to pass (empty errors list)
        validator.validate.return_value = []

        # Path exists for meta.yaml check in session mode
        fs_mock.path_exists.return_value = True

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

        plan_path = ".teddy/sessions/test/01/plan.md"

        # Act: execute with empty message
        result = orchestrator.execute(
            message="",
            plan_path=plan_path,
            interactive=False,
        )

        # Assert: termination signal (None) returned
        assert result is None, "Empty message should return None to signal termination"

        # Assert: no report.md was written
        report_writes = [
            call
            for call in fs_mock.write_file.call_args_list
            if call[0][0].endswith("report.md")
        ]
        assert len(report_writes) == 0, (
            f"No report.md should be written on empty message; found {len(report_writes)}"
        )

        # Assert: finalize_turn was NOT called
        assert lifecycle_mgr.finalize_turn.call_count == 0, (
            "finalize_turn should not be called on empty message termination"
        )
