"""Unit tests: pipeline MESSAGE turn suppression in SessionOrchestrator.

Regression coverage for the pipeline (-p) final-turn defect: a session
turn that ends with a MESSAGE action must NOT be finalized — no report.md
write via finalize_turn, no next-turn transition — and the current turn's
meta must be flagged with "awaiting_reply: true" so the session stays
resumable in a clean awaiting-reply state. Non-pipeline MESSAGE turns
(interactive/YOLO) and pipeline turns without a MESSAGE keep the existing
finalization behavior.
"""

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import punq

from teddy_executor.core.domain.models import Plan
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
    RunStatus,
    RunSummary,
)
from teddy_executor.core.ports.inbound.get_context_use_case import IGetContextUseCase
from teddy_executor.core.ports.inbound.plan_parser import IPlanParser
from teddy_executor.core.ports.inbound.plan_validator import IPlanValidator
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.config_service import IConfigService
from teddy_executor.core.ports.outbound.file_system_manager import IFileSystemManager
from teddy_executor.core.ports.outbound.llm_client import ILlmClient
from teddy_executor.core.ports.outbound.prompt_manager import IPromptManager
from teddy_executor.core.ports.outbound.user_interactor import IUserInteractor
from teddy_executor.core.services.session_lifecycle_manager import (
    SessionLifecycleManager,
)
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator
from teddy_executor.core.services.session_replanner import SessionReplanner
from teddy_executor.core.services.session_service import SessionService
from tests.harness.drivers.plan_builder import MarkdownPlanBuilder
from tests.harness.setup.mocking import register_mock

PLAN_PATH = ".teddy/sessions/20260417_120000-feature/01/plan.md"
TURN_DIR = str(Path(PLAN_PATH).parent)


def _build_harness() -> SimpleNamespace:
    """Builds SessionOrchestrator with strictly bound mock dependencies.

    Mirrors the direct-construction recipe of the empty-message termination
    tests: a fresh punq.Container registry plus register_mock autospecs for
    every constructor dependency (no bare MagicMock). The plan is a spec'd
    mock so is_communication_turn can be toggled per scenario; the report
    handed back by the execution orchestrator is a REAL ExecutionReport.
    """
    container = punq.Container()
    fs_mock = register_mock(container, IFileSystemManager)
    exec_orch = register_mock(container, IRunPlanUseCase)
    session_svc = register_mock(container, SessionService)
    validator = register_mock(container, IPlanValidator)
    parser = register_mock(container, IPlanParser)
    interactor = register_mock(container, IUserInteractor)
    lifecycle_mgr = register_mock(container, SessionLifecycleManager)
    replanner = register_mock(container, SessionReplanner)
    context_svc = register_mock(container, IGetContextUseCase)
    config_svc = register_mock(container, IConfigService)
    llm_client = register_mock(container, ILlmClient)
    prompt_mgr = register_mock(container, IPromptManager)
    plan = register_mock(container, Plan)

    # Session mode is detected via meta.yaml existence; parsing yields the
    # plan mock and validation passes through.
    fs_mock.path_exists.return_value = True
    parser.parse.return_value = plan
    validator.validate.return_value = []
    plan.metadata = {}

    # Inert context-prep surfaces (mirrors the established orchestrator fixture).
    prompt_mgr.fetch_system_prompt.return_value = "mock prompt content"
    llm_client.get_text_token_count.return_value = 100
    # Default turn meta for the suppression path (overridden per scenario).
    session_svc.load_turn_meta.return_value = {}

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
    return SimpleNamespace(
        orchestrator=orchestrator,
        plan=plan,
        execution_orchestrator=exec_orch,
        lifecycle_manager=lifecycle_mgr,
        session_service=session_svc,
    )


def _make_report(message_details: str | None) -> ExecutionReport:
    """Builds a SUCCESS report, optionally carrying one MESSAGE action log."""
    logs: list[ActionLog] = []
    if message_details is not None:
        logs.append(
            ActionLog(
                status=ActionStatus.SUCCESS,
                action_type="MESSAGE",
                params={},
                details=message_details,
            )
        )
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        run_summary=RunSummary(status=RunStatus.SUCCESS, start_time=now, end_time=now),
        plan_title="Message Turn",
        action_logs=logs,
    )


class TestPipelineMessageSuppression:
    """Pipeline MESSAGE turns must stop without finalizing the turn."""

    def test_pipeline_message_turn_skips_finalization_and_returns_report(self) -> None:
        # Arrange
        h = _build_harness()
        h.plan.is_communication_turn.return_value = True
        report = _make_report("Hello from the pipeline! How are you?")
        h.execution_orchestrator.execute.return_value = report

        # Act
        result = h.orchestrator.execute(
            plan_content=MarkdownPlanBuilder("Message turn").build(),
            plan_path=PLAN_PATH,
            interactive=False,
            pipeline=True,
        )

        # Assert: the turn is NOT finalized (no report.md, no next turn).
        h.lifecycle_manager.finalize_turn.assert_not_called()
        h.session_service.transition_to_next_turn.assert_not_called()
        # Assert: the report is returned so the CLI pipeline break fires.
        assert result is report

    def test_pipeline_message_turn_flags_awaiting_reply_over_loaded_meta(self) -> None:
        # Arrange
        h = _build_harness()
        h.plan.is_communication_turn.return_value = True
        h.session_service.load_turn_meta.return_value = {
            "agent_name": "assistant",
            "turn_id": "01",
            "cumulative_cost": 0.25,
        }
        h.execution_orchestrator.execute.return_value = _make_report(
            "Awaiting your reply."
        )

        # Act
        h.orchestrator.execute(
            plan_content=MarkdownPlanBuilder("Message turn").build(),
            plan_path=PLAN_PATH,
            interactive=False,
            pipeline=True,
        )

        # Assert: awaiting_reply is persisted as a merge over the loaded meta
        # (load-modify-save), targeting the message turn's directory.
        h.session_service.save_turn_meta.assert_called_once_with(
            TURN_DIR,
            {
                "agent_name": "assistant",
                "turn_id": "01",
                "cumulative_cost": 0.25,
                "awaiting_reply": True,
            },
        )
        h.session_service.load_turn_meta.assert_called_once_with(TURN_DIR)

    def test_pipeline_turn_without_message_still_finalizes(self) -> None:
        # Arrange
        h = _build_harness()
        h.plan.is_communication_turn.return_value = False
        report = _make_report(None)
        h.execution_orchestrator.execute.return_value = report

        # Act
        h.orchestrator.execute(
            plan_content=MarkdownPlanBuilder("Action turn").build(),
            plan_path=PLAN_PATH,
            interactive=False,
            pipeline=True,
        )

        # Assert: pipeline alone must not suppress regular turn finalization.
        h.lifecycle_manager.finalize_turn.assert_called_once_with(
            PLAN_PATH, report, plan=h.plan
        )
        h.session_service.save_turn_meta.assert_not_called()

    def test_non_pipeline_message_turn_still_finalizes(self) -> None:
        # Arrange
        h = _build_harness()
        h.plan.is_communication_turn.return_value = True
        report = _make_report("Interactive reply")
        h.execution_orchestrator.execute.return_value = report

        # Act
        h.orchestrator.execute(
            plan_content=MarkdownPlanBuilder("Message turn").build(),
            plan_path=PLAN_PATH,
            interactive=False,
            pipeline=False,
        )

        # Assert: interactive/YOLO MESSAGE turns keep the existing audit trail.
        h.lifecycle_manager.finalize_turn.assert_called_once_with(
            PLAN_PATH, report, plan=h.plan
        )
        h.session_service.save_turn_meta.assert_not_called()
