"""
Regression test for Bug 40: 'q' Cancel Message Not Logged as User Message in Terminal.

Tests that when an execution report has ABORTED status, the abort prompt captures
a user message, and _print_user_message is called with that captured message
(proving the ordering is correct: abort handling before printing).
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock as _MagicMock, patch as _patch  # noqa: TID251
import os
import tempfile

from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunSummary,
    RunStatus,
)
from teddy_executor.core.domain.models.plan import Plan
from teddy_executor.core.services.session_orchestrator import SessionOrchestrator


# ---- Helper: create a valid Plan with at least one action ----
def make_valid_plan() -> Plan:
    from teddy_executor.core.domain.models.plan import ActionData

    # ActionData stores action_number and total_actions in params["action_number"] etc.
    # The constructor accepts: type, params, selected, etc.
    # We use a MESSAGE type with minimal params to satisfy Plan's __post_init__ assertion.
    dummy_action = ActionData(
        type="MESSAGE",
        params={},
        selected=True,
    )
    plan = Plan(
        title="Test Plan",
        actions=[dummy_action],
        source_doc=None,
        rationale="Testing abort flow",
        is_session=True,
    )
    plan.metadata = {}
    return plan


# ---- Helper: create an ExecutionReport with ABORTED status ----
def make_abort_report() -> ExecutionReport:
    now = datetime.now(timezone.utc)
    return ExecutionReport(
        plan_title="Test Plan",
        run_summary=RunSummary(
            status=RunStatus.ABORTED,
            start_time=now,
            end_time=now,
        ),
        action_logs=[],
        metadata={},
    )


def build_mocks():
    """Build standard mocks for SessionOrchestrator dependencies."""
    exec_orch = _MagicMock()
    exec_orch.execute.return_value = make_abort_report()
    session_svc = _MagicMock()
    fs_manager = _MagicMock()
    fs_manager.path_exists.return_value = True  # meta.yaml exists → is_session
    fs_manager.open_file_for_append.return_value = _MagicMock()
    plan_validator = _MagicMock()
    plan_validator.validate.return_value = []
    plan_parser = _MagicMock()
    plan_parser.parse.return_value = make_valid_plan()
    user_interactor = _MagicMock()
    user_interactor.ask_question.return_value = "My cancel reason"
    lifecycle_mgr = _MagicMock()
    lifecycle_mgr.tee_active = False
    replanner = _MagicMock()
    context_svc = _MagicMock()
    config_svc = _MagicMock()
    config_svc.get_setting.return_value = "test-model"
    llm_client = _MagicMock()
    llm_client.get_context_window.return_value = 8000
    prompt_mgr = _MagicMock()
    prompt_mgr.fetch_system_prompt.return_value = "system prompt"
    pruning_svc = _MagicMock()

    return {
        "execution_orchestrator": exec_orch,
        "session_service": session_svc,
        "file_system_manager": fs_manager,
        "plan_validator": plan_validator,
        "plan_parser": plan_parser,
        "user_interactor": user_interactor,
        "lifecycle_manager": lifecycle_mgr,
        "replanner": replanner,
        "context_service": context_svc,
        "config_service": config_svc,
        "llm_client": llm_client,
        "prompt_manager": prompt_mgr,
        "pruning_service": pruning_svc,
    }


class TestQCancelMessageTerminalOutput:
    """Tests for Bug 40: abort message printed to terminal."""

    def test_q_abort_message_printed_to_terminal(self):
        """
        When an execution report has ABORTED status, _handle_aborted_session
        should capture the user's cancel message, and _print_user_message
        should be called with that message (proving the ordering is correct:
        abort handling before printing).
        """
        mocks = build_mocks()

        # Track calls to _print_user_message
        call_history = []

        def _track_print_user_message(message, is_session, **kwargs):
            call_history.append(("_print_user_message", message, is_session, kwargs))

        orchestrator = SessionOrchestrator(**mocks)

        # Patch _print_user_message and _handle_aborted_session
        fake_plan_path = os.path.join(
            tempfile.gettempdir(), "fake_session", "turns", "001", "plan.md"
        )
        with _patch(
            "teddy_executor.core.services.session_orchestrator._print_user_message",
            side_effect=_track_print_user_message,
        ):
            plan = make_valid_plan()
            orchestrator.execute(
                plan=plan,
                plan_path=fake_plan_path,
                interactive=False,
            )

        # _handle_aborted_session should have been called (it's a real method,
        # not mocked), which means it prompted the user and stored "My cancel reason"
        # in plan.metadata["user_request"].
        # After the fix, _print_user_message should be called AFTER _handle_aborted_session,
        # so it should see "My cancel reason" in plan.metadata.
        assert len(call_history) >= 1, (
            "_print_user_message was not called at all. "
            "This may indicate the abort flow was never triggered."
        )

        # The last call to _print_user_message should have the cancel message
        last_call = call_history[-1]
        assert last_call[0] == "_print_user_message", "Unexpected call order"
        # message parameter (positional arg 1) should be "My cancel reason"
        assert last_call[1] == "My cancel reason", (
            f"Expected 'My cancel reason' but got '{last_call[1]}'. "
            "This suggests _print_user_message was called before "
            "_handle_aborted_session populated the metadata."
        )

    def test_q_abort_message_appears_in_report_metadata(self):
        """
        The abort message should also be stored in the report metadata
        so it appears in report.md.
        """
        mocks = build_mocks()

        orchestrator = SessionOrchestrator(**mocks)

        fake_plan_path = os.path.join(
            tempfile.gettempdir(), "fake_session", "turns", "001", "plan.md"
        )
        with _patch(
            "teddy_executor.core.services.session_orchestrator._print_user_message",
        ):
            plan = make_valid_plan()
            report = orchestrator.execute(
                plan=plan,
                plan_path=fake_plan_path,
                interactive=False,
            )

        assert report is not None, "Report should not be None"
        assert report.run_summary.status == RunStatus.ABORTED
        assert report.user_request == "My cancel reason", (
            f"Expected 'My cancel reason' in report.user_request, got '{report.user_request}'"
        )
        assert report.metadata.get("user_request") == "My cancel reason", (
            "Report metadata should also contain the user_request"
        )
