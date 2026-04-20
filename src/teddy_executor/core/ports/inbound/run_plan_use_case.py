from abc import ABC, abstractmethod
from typing import Optional
from teddy_executor.core.domain.models import ExecutionReport, Plan


class IRunPlanUseCase(ABC):
    """
    Defines the contract for running a teddy execution plan.
    """

    @abstractmethod
    def execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        """
        Executes a plan and returns a report.

        Args:
            plan: An already parsed Plan object.
            plan_content: Raw Markdown content of a plan.
            plan_path: Path to a plan file on disk.
            interactive: A flag to enable/disable step-by-step user approval.
            message: Optional user instruction to include in the report.
        """
        pass

    @abstractmethod
    def resume(
        self,
        session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """
        Intelligently resumes the session based on its state.

        Args:
            session_name: The name of the session to resume.
            interactive: Whether to run in interactive mode.
            message: Optional user instruction to bridge to the next turn.
        """
        pass

    @abstractmethod
    async def async_execute(
        self,
        plan: Optional[Plan] = None,
        plan_content: Optional[str] = None,
        plan_path: Optional[str] = None,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> ExecutionReport:
        """
        Asynchronously executes a plan and returns a report.
        """
        pass

    @abstractmethod
    async def async_resume(
        self,
        session_name: str,
        interactive: bool = True,
        message: Optional[str] = None,
    ) -> Optional[ExecutionReport]:
        """
        Asynchronously resumes the session based on its state.
        """
        pass
