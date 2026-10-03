import logging
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

import yaml
from teddy_executor.core.domain.models.execution_report import (
    ActionLog,
    ActionStatus,
    ExecutionReport,
)
from teddy_executor.core.domain.models.plan import ActionType
from teddy_executor.core.domain.models.report_assembly_data import ReportAssemblyData

from typing import Sequence

from teddy_executor.core.ports.inbound.plan_parser import InvalidPlanError
from teddy_executor.core.ports.inbound.run_plan_use_case import IRunPlanUseCase
from teddy_executor.core.ports.outbound.session_manager import SessionState
from teddy_executor.core.utils.io import Tee as _Tee
from teddy_executor.core.utils.markdown import get_fence_for_content

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.planning_ports import (
        SessionPorts,
    )
    from teddy_executor.core.domain.models.plan import Plan

    _ = SessionPorts


class SessionLifecycleManager:
    """
    Manages the lifecycle of session turns, including finalization,
    resume state machine, and automated re-plan coordination.
    """

    tee_active = False  # Class-level default for mock spec compatibility

    def __init__(self, ports: "SessionPorts"):
        self._session_service = ports.session_service
        self._file_system_manager = ports.file_system_manager
        self._report_formatter = ports.report_formatter
        self._user_interactor = ports.user_interactor
        self._session_planner = ports.session_planner
        self._replanner = ports.replanner
        self._plan_parser = ports.plan_parser
        self._time_service = ports.time_service
        self._report_assembler = ports.report_assembler
        self.tee_active = False

    def resume(
        self,
        session_name: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool = True,
        project_context: Optional[Any] = None,
        pipeline: bool = False,
        message: Optional[str] = None,
    ) -> tuple[str, Optional[ExecutionReport]]:
        """Implements the 'resume' state machine.

        Returns:
            A tuple (actual_session_name, report). The actual_session_name
            may differ from the input session_name after a centennial
            migration (when the session transitions to a continuation name
            like 'my-session-2').
        """
        state, turn_path = self._session_service.get_session_state(session_name)

        if state == SessionState.PENDING_PLAN:
            turn_meta = self._session_service.load_turn_meta(turn_path)
            if self._should_consume_awaiting_reply(turn_meta, turn_path, message):
                return self._consume_awaiting_reply(
                    turn_path,
                    turn_meta,
                    session_name,
                    orchestrator,
                    interactive,
                    project_context=project_context,
                    pipeline=pipeline,
                    message=message,
                )
            plan_path = f"{turn_path}/plan.md"
            plan = self._seed_pending_plan(turn_path, plan_path, message)
            if plan is not None:
                report = orchestrator.execute(
                    plan=plan,
                    plan_path=plan_path,
                    interactive=interactive,
                    project_context=project_context,
                    pipeline=pipeline,
                )
            else:
                report = orchestrator.execute(
                    plan_path=plan_path,
                    interactive=interactive,
                    project_context=project_context,
                    pipeline=pipeline,
                )
            return (session_name, report)

        if state == SessionState.EMPTY:
            if message:
                self._append_message_to_previous_turn(turn_path, message)
            return self._handle_planning_and_execution(
                turn_path,
                orchestrator,
                interactive,
                project_context=project_context,
                pipeline=pipeline,
                message=message,
            )

        if state == SessionState.COMPLETE_TURN:
            if message:
                self._append_user_request(turn_path, message)
            next_turn_dir = self._session_service.transition_to_next_turn(
                plan_path=f"{turn_path}/plan.md"
            )
            return self._handle_planning_and_execution(
                next_turn_dir,
                orchestrator,
                interactive,
                project_context=project_context,
                message=message,
            )

        return (session_name, None)

    def _is_communication_turn(self, turn_path: str) -> bool:
        """Reports whether the pending turn's plan is a MESSAGE-only turn.

        An interactively-interrupted MESSAGE turn lands in PENDING_PLAN
        WITHOUT the awaiting_reply flag (only the pipeline-stop path sets
        it). Such a turn is semantically awaiting a reply, so an injected
        `resume -m` reply must be consumed (mirroring
        `_consume_awaiting_reply`) rather than dropped while the MESSAGE
        plan is re-executed and re-prompts the user. Unparseable or
        non-communication plans degrade gracefully to the re-execute path.
        """
        try:
            plan = self._parse_awaiting_plan(turn_path)
        except Exception:
            return False
        return plan.is_communication_turn()

    def _should_consume_awaiting_reply(
        self, turn_meta: dict[str, Any], turn_path: str, message: Optional[str]
    ) -> bool:
        """Reports whether the pending turn's reply must be consumed.

        A reply is consumed when the turn carries the ``awaiting_reply``
        flag (pipeline stop) or when an injected reply lands on a MESSAGE-
        only communication turn (an interactively-interrupted communication
        turn lacks the flag but is semantically awaiting a reply). A plain
        pending action turn with no reply falls through to re-execution.
        """
        return bool(turn_meta.get("awaiting_reply")) or (
            bool(message) and self._is_communication_turn(turn_path)
        )

    def _seed_pending_plan(
        self, turn_path: str, plan_path: str, message: Optional[str]
    ) -> Optional["Plan"]:
        """Parses the pending plan (WITH its path) and seeds the injected reply.

        Parsing WITH ``plan_path`` preserves ``Plan.is_session`` /
        ``Plan.plan_path`` — ``execute(plan=...)`` short-circuits
        re-resolution from the path. Returns ``None`` when no reply is
        injected or when the plan is unparseable, so the caller falls back to
        the bare re-execute path. The reply is seeded onto the plan's
        metadata (never forwarded as ``message``) so a TUI edit can still
        override it.
        """
        if not message:
            return None
        try:
            plan = self._parse_awaiting_plan(turn_path, plan_path=plan_path)
        except InvalidPlanError:
            logger.debug(
                "Pending plan at %s is unparseable; falling back to the "
                "re-execute path.",
                plan_path,
            )
            return None
        plan.metadata["user_request"] = message
        return plan

    def _append_message_to_previous_turn(self, turn_path: str, message: str) -> None:
        """Appends the injected reply to the previous turn's report if present.

        The EMPTY state's turn is the successor pre-created by the previous
        turn's finalization; the injected reply is appended to that previous
        turn's report when it exists. Turn ``01`` (or a missing report) is a
        no-op — planning still carries the message.
        """
        turn_name = Path(turn_path).name
        if not turn_name.isdigit():
            return
        parent = Path(turn_path).parent
        prev_turn = str(parent / f"{int(turn_name) - 1:02d}")
        prev_report = self._session_service.to_root_relative(
            Path(prev_turn), "report.md"
        )
        if self._file_system_manager.path_exists(prev_report):
            self._append_user_request(prev_turn, message)

    def _append_user_request(self, turn_path: str, message: str) -> None:
        """Appends a smart-fenced `## User Request` section to the turn report.

        Mirrors the execution_report.md.j2 User Request format (heading +
        smart-fenced codeblock whose opening fence carries the "text"
        language suffix and whose closing fence is bare) so session_service's
        `^## User Request` detection regex recognizes the turn as a
        user-request turn.
        """
        report_path = self._session_service.to_root_relative(
            Path(turn_path), "report.md"
        )
        assert self._file_system_manager.path_exists(report_path), (
            f"Cannot append user request: report not found at {report_path}"
        )
        content = str(self._file_system_manager.read_file(report_path)).rstrip("\n")
        fence = get_fence_for_content(message)
        content += f"\n\n## User Request\n{fence}text\n{message}\n{fence}\n"
        self._file_system_manager.write_file(report_path, content)

    def _consume_awaiting_reply(
        self,
        turn_path: str,
        turn_meta: dict[str, Any],
        session_name: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool,
        project_context: Optional[Any] = None,
        pipeline: bool = False,
        message: Optional[str] = None,
    ) -> tuple[str, Optional[ExecutionReport]]:
        """Consumes an awaiting-reply turn without re-executing its plan.

        A pipeline MESSAGE turn stops before finalization (plan.md present,
        no report.md, awaiting_reply flagged). The user's reply — injected
        via `resume -m` or prompted interactively (mirroring the abort
        flow) — drives the next turn's planning; the awaiting_reply flag is
        cleared on consumption via load-modify-save.
        """
        reply = message
        if not reply and interactive:
            reply = self._user_interactor.ask_question(
                "The agent is awaiting your reply. How do you want to proceed?"
            )
            if not reply:
                # Empty reply terminates the session (abort-flow idiom);
                # the awaiting state is preserved (flag NOT cleared).
                return (session_name, None)
        if not reply and pipeline:
            # Case 2 stop-again: re-print the agent's MESSAGE and exit,
            # preserving the awaiting state (no meta mutation, no
            # finalization, no next turn) so a later `resume -p -m` can
            # inject the reply. The re-print reuses the SAME shared
            # rendering as the pipeline-start path (status header + CYAN
            # framing + body) so the two presentations match
            # (Bug 54 / defect 4a).
            from teddy_executor.core.services.session_orchestrator import (
                _print_header_bar,
                _print_message_from_teddy,
            )

            plan = self._parse_awaiting_plan(turn_path)
            report = self._synthesize_message_report(turn_path, plan=plan)
            message_logs = [
                log for log in report.action_logs if log.action_type == "MESSAGE"
            ]
            assert message_logs, (
                "Synthesized message report must carry a MESSAGE action log."
            )
            content = str(message_logs[0].params.get("content", ""))
            _print_header_bar(plan, True)
            _print_message_from_teddy(content)
            return (session_name, report)
        if not reply:
            self._user_interactor.display_message(
                "This session is awaiting your reply. Re-run interactively "
                "or inject one with: teddy resume -m '<your reply>'"
            )
            return (session_name, None)
        consumed_meta = {
            key: value for key, value in turn_meta.items() if key != "awaiting_reply"
        }
        self._session_service.save_turn_meta(turn_path, consumed_meta)
        report = self._synthesize_message_report(turn_path, reply=reply)
        next_turn_dir = self.finalize_turn(f"{turn_path}/plan.md", report)
        return self._handle_planning_and_execution(
            next_turn_dir,
            orchestrator,
            interactive,
            project_context=project_context,
            pipeline=pipeline,
            message=reply,
        )

    def _parse_awaiting_plan(
        self, turn_path: str, plan_path: Optional[str] = None
    ) -> "Plan":
        """Parse the interrupted turn's plan.md.

        A pipeline MESSAGE turn stops before finalization; its plan is
        re-parsed on consumption for BOTH the report synthesis and, on the
        stop-again path, the status header. Shared by the consumption
        branches so plan.md is parsed exactly once per resume.

        When ``plan_path`` is supplied it is forwarded to the parser so
        ``Plan.plan_path``/``Plan.is_session`` survive a parse whose result
        is later handed to ``orchestrator.execute(plan=...)`` (which
        short-circuits re-resolution from the path). Existing callers omit
        it and keep the original path-less behaviour byte-identical.
        """
        assert self._plan_parser is not None, (
            "SessionPorts.plan_parser must be injected to synthesize the "
            "awaiting-reply turn's report."
        )
        content = str(self._file_system_manager.read_file(f"{turn_path}/plan.md"))
        if plan_path is None:
            return self._plan_parser.parse(content)
        return self._plan_parser.parse(content, plan_path=plan_path)

    def _synthesize_message_report(
        self,
        turn_path: str,
        reply: Optional[str] = None,
        plan: Optional["Plan"] = None,
    ) -> ExecutionReport:
        """Synthesizes the standard message-turn report from the interrupted plan.

        A pipeline MESSAGE turn stops before finalization, so its report is
        reconstructed from plan.md on consumption: the plan is parsed via
        the injected IPlanParser (or supplied by the caller to avoid a
        second parse), the MESSAGE action's content becomes the report's
        single MESSAGE action log, and the injected
        IExecutionReportAssembler builds the report from that plan and log
        (the injected ITimeService supplies the start timestamp). The
        standard message-turn shape is therefore guaranteed by the SAME
        assembler every other finalized turn uses (NO ## User Request
        section: the consumption path never appends; the interrupted turn
        has no prior report).

        Canonical `details` semantics: a MESSAGE ActionLog's `details` holds
        the USER's reply (rendered under `- **User Reply:**`), while the
        agent's own text lives in `params["content"]` (render-ignored). The
        injected `reply` is therefore stored in `details`; the stop-again
        path passes none (no user reply yet, `details` stays empty so the
        agent's message is never mislabeled as the user's reply).
        """
        assert self._time_service is not None, (
            "SessionPorts.time_service must be injected to synthesize the "
            "awaiting-reply turn's report."
        )
        assert self._report_assembler is not None, (
            "SessionPorts.report_assembler must be injected to synthesize the "
            "awaiting-reply turn's report."
        )
        if plan is None:
            plan = self._parse_awaiting_plan(turn_path)
        plan_path = f"{turn_path}/plan.md"
        message_actions = [
            action for action in plan.actions if action.type == ActionType.MESSAGE
        ]
        assert message_actions, (
            f"Awaiting-reply turn's plan at {plan_path} must contain a MESSAGE action."
        )
        content = str(message_actions[0].params.get("content", ""))
        timestamp = self._time_service.now_utc()
        return self._report_assembler.assemble(
            ReportAssemblyData(
                plan=plan,
                action_logs=[
                    ActionLog(
                        status=ActionStatus.SUCCESS,
                        action_type="MESSAGE",
                        params={"content": content},
                        details=reply,
                    )
                ],
                start_time=timestamp,
            )
        )

    def _handle_planning_and_execution(
        self,
        turn_dir: str,
        orchestrator: IRunPlanUseCase,
        interactive: bool,
        project_context: Optional[Any] = None,
        pipeline: bool = False,
        message: Optional[str] = None,
    ) -> tuple[str, Optional[ExecutionReport]]:
        """Triggers planning for a turn and then executes the resulting plan.

        An injected message (resume -m / prompted reply) is threaded into
        trigger_new_plan so planning skips the interactive prompt.

        Tee is installed before planning to capture all output (turn headers,
        metadata, planning logs) into history.log. The installation is guarded
        by tee_active to prevent double installation.

        Returns:
            A tuple (actual_session_name, report). The actual_session_name
            is the session name returned by trigger_new_plan, which may
            differ from the original session name after a centennial
            migration.
        """
        # Install Tee to capture planning output before trigger_new_plan
        tee = None
        if not self.tee_active:
            try:
                log_path = str(Path(turn_dir).parent / "history.log")
                # Defensive guard: never write history.log to project root
                resolved = str(Path(log_path).resolve())
                project_root = str(Path.cwd().resolve())
                if resolved.rstrip("/") == project_root.rstrip("/"):
                    safe_dir = str(Path(turn_dir).parent.parent / ".tmp")
                    self._file_system_manager.create_directory(safe_dir)
                    log_path = str(Path(safe_dir) / "history.log")
                log_file = self._file_system_manager.open_file_for_append(log_path)
                tee = _Tee(log_file)
                tee.__enter__()
                self.tee_active = True
            except Exception:
                logger.warning("Failed to install Tee in lifecycle manager")
                tee = None

        try:
            # Print initial request before turn header (before planning)
            from teddy_executor.core.services.session_orchestrator import (
                _print_initial_request,
            )

            if Path(turn_dir).name == "01":
                _print_initial_request(None, True, plan_path=Path(turn_dir).as_posix())
            new_name, gathered_context = self._session_planner.trigger_new_plan(
                turn_dir, message=message
            )
            if not new_name or new_name == "CANCELLED":
                return (turn_dir, None)
            _, actual_turn_path = self._session_service.get_session_state(new_name)
            report = orchestrator.execute(
                plan_path=f"{actual_turn_path}/plan.md",
                interactive=interactive,
                project_context=(
                    gathered_context
                    if gathered_context is not None
                    else project_context
                ),
                pipeline=pipeline,
            )
            return (new_name, report)
        finally:
            self.tee_active = False
            if tee is not None:
                try:
                    tee.__exit__(None, None, None)
                except Exception:
                    logger.exception("Failed to clean up Tee in lifecycle manager")

    def trigger_replan(  # noqa: PLR0913
        self,
        plan_path: str,
        errors: list[str],
        original_plan_content: str,
        title: str = "Unknown Plan",
        rationale: str = "Structural Error",
        failed_resources: Optional[dict[str, str]] = None,
        is_session: bool = False,
        validation_ast: Optional[str] = None,
        original_actions: Optional[Sequence[Any]] = None,
        plan: Optional["Plan"] = None,
    ) -> ExecutionReport:
        """Triggers the Automated Re-plan Loop."""
        self._user_interactor.display_message(
            "[yellow]Validation failed... replanning[/yellow]"
        )
        report = self._replanner.build_failure_report(
            errors,
            title,
            rationale,
            failed_resources or {},
            validation_ast=validation_ast,
            original_actions=original_actions,
            is_session=is_session,
        )
        next_turn_dir = self.finalize_turn(
            plan_path, report, is_validation_failure=True, plan=plan
        )

        self._replanner.trigger_replan_turn(
            next_turn_dir, errors, original_plan_content, validation_ast=validation_ast
        )
        return report

    def finalize_turn(
        self,
        plan_path: str,
        report: ExecutionReport,
        is_validation_failure: bool = False,
        plan: Optional[Any] = None,
    ) -> str:
        """Persists the report and transitions to the next turn."""
        turn_dir = Path(plan_path).parent
        meta_path = turn_dir / "meta.yaml"

        # Read current cost from meta.yaml
        turn_cost = 0.0
        if self._file_system_manager.path_exists(str(meta_path)):
            meta_content = self._file_system_manager.read_file(str(meta_path))
            meta_loaded = yaml.safe_load(str(meta_content))
            meta = meta_loaded if isinstance(meta_loaded, dict) else {}
            turn_cost = meta.get("turn_cost", 0.0)

        # 1. Persist the report to the current turn directory
        formatted_report = self._report_formatter.format(report)
        # Use root-relative path for report persistence to ensure context discovery
        report_file_path = self._session_service.to_root_relative(turn_dir, "report.md")
        self._file_system_manager.write_file(report_file_path, formatted_report)

        # Extract manual pruning paths from plan metadata
        pruned_paths = []
        if plan:
            raw_pruned = plan.metadata.get("pruned_context", "")
            if raw_pruned:
                pruned_paths = [p.strip() for p in raw_pruned.split(",") if p.strip()]

        # 2. Transition to next turn
        return self._session_service.transition_to_next_turn(
            plan_path=plan_path,
            execution_report=report,
            turn_cost=turn_cost,
            is_validation_failure=is_validation_failure,
            pruned_paths=pruned_paths,
        )
