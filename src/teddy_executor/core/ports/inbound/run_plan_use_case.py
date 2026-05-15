from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from teddy_executor.core.domain.models import ExecutionReport, Plan

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.project_context import ProjectContext


class IRunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(  # noqa: PLR0913
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
        project_context: Optional["ProjectContext"] = None,
    ) -> ExecutionReport:
        """
        Executes a plan and returns a report.

        Args:
            plan: An already parsed Plan object.
            plan_content: Raw Markdown content of a plan.
            plan_path: Path to a plan file on disk.
            interactive: A flag to enable/disable step-by-step user approval.
            message: Optional user instruction to include in the report.
            project_context: Optional context metadata for display and auto-pruning.
        """
        _ = (plan, plan_content, plan_path, interactive, message, project_context)
        raise NotImplementedError

    @abstractmethod
    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        project_context: Optional["ProjectContext"] = None,
    ) -> Optional[ExecutionReport]:
        """
        Intelligently resumes the session based on its state.

        Args:
            session_name: The name of the session to resume.
            interactive: Whether to run in interactive mode.
        """
        _ = (session_name, interactive, project_context)
        raise NotImplementedError
