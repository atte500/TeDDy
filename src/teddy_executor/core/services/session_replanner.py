from datetime import datetime, timezone
from typing import Any, Sequence

from teddy_executor.core.domain.models.execution_report import (
    ExecutionReport,
    RunStatus,
    RunSummary,
)


class SessionReplanner:
    """
    Orchestrates the feedback and planning logic for the Automated Re-plan Loop.
    """

    def __init__(self, file_system_manager, planning_service):
        self._file_system_manager = file_system_manager
        self._planning_service = planning_service

    def build_failure_report(  # noqa: PLR0913
        self,
        errors: list[str],
        title: str,
        rationale: str,
        failed_resources: dict[str, str],
        validation_ast: str | None = None,
        original_actions: Sequence[Any] | None = None,
    ) -> ExecutionReport:
        """Creates a validation failure report."""
        now = datetime.now(timezone.utc)
        summary = RunSummary(
            status=RunStatus.VALIDATION_FAILED,
            start_time=now,
            end_time=now,
            error="Plan validation failed.",
        )
        return ExecutionReport(
            run_summary=summary,
            plan_title=title,
            rationale=rationale,
            original_actions=original_actions or [],
            action_logs=[],
            validation_result=errors,
            validation_ast=validation_ast,
            failed_resources=failed_resources,
        )

    def trigger_replan_turn(
        self,
        next_turn_dir: str,
        errors: list[str],
        original_content: str,
        validation_ast: str | None = None,
    ) -> None:
        """Generates the feedback message and triggers the planning phase."""
        error_msgs = [e.strip() for e in errors]
        ast_section = f"\n{validation_ast}\n" if validation_ast else ""

        feedback = (
            "The previous plan failed validation. Please review the errors and "
            "the original plan, then generate a corrected version.\n\n"
            "## Validation Errors:\n"
            + "\n\n---\n\n".join(error_msgs)
            + "\n"
            + ast_section
            + "\n"
            f"## Original Faulty Plan:\n"
            f"````````````markdown\n{original_content}\n````````````"
        )
        self._planning_service.generate_plan(
            user_message=feedback, turn_dir=next_turn_dir
        )

    def gather_failed_resources(self, errors: list) -> dict[str, str]:
        """Collects the contents of files that caused validation errors."""
        resources = {}
        for error in errors:
            path = getattr(error, "file_path", None)
            if path:
                try:
                    clean_path = path.lstrip("/")
                    if self._file_system_manager.path_exists(clean_path):
                        resources[path] = self._file_system_manager.read_file(
                            clean_path
                        )
                except Exception:  # nosec B112
                    # Best effort resource gathering; skip if file is unreadable
                    continue
        return resources
