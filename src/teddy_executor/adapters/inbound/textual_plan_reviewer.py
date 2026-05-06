from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

from teddy_executor.adapters.inbound.textual_plan_reviewer_app import ReviewerApp
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

if TYPE_CHECKING:
    from teddy_executor.adapters.outbound.console_tooling import ConsoleToolingHelper
    from teddy_executor.core.domain.models.plan import ActionData, Plan
    from teddy_executor.core.domain.models.project_context import ProjectContext
    from teddy_executor.core.ports.outbound.file_system_manager import (
        IFileSystemManager,
    )
    from teddy_executor.core.ports.outbound.system_environment import ISystemEnvironment
    from teddy_executor.core.services.action_dispatcher import ActionDispatcher


class TextualPlanReviewer(IPlanReviewer):
    """
    Implements IPlanReviewer using the Textual TUI framework.
    """

    def __init__(
        self,
        system_env: ISystemEnvironment,
        file_system: IFileSystemManager,
        console_tooling: ConsoleToolingHelper,
        action_dispatcher: ActionDispatcher,
    ):
        self._system_env = system_env
        self._file_system = file_system
        self._console_tooling = console_tooling
        self._action_dispatcher = action_dispatcher

    def review(
        self, plan: Plan, project_context: Optional[ProjectContext] = None
    ) -> Optional[Plan]:
        """
        Initiates the interactive review process using the Textual TUI.
        """
        return self._run_app(plan)

    def review_action(
        self,
        action: "ActionData",
        _total_actions: int,
        agent_name: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        For the TUI, per-action review is handled in bulk by review_plan.
        This method always returns True to allow the loop to proceed with selections.
        """
        _ = agent_name  # Mark as used for vulture
        return True, ""

    def _run_app(self, plan: Plan) -> Optional[Plan]:
        """
        Internal helper to launch the Textual app.
        Separated to allow for easier testing and mocking.
        """
        app = ReviewerApp(
            plan=plan,
            system_env=self._system_env,
            console_tooling=self._console_tooling,
            action_dispatcher=self._action_dispatcher,
            file_system=self._file_system,
        )
        result = app.run()
        if os.getenv("TEDDY_DEBUG") and result:
            print(
                f"\n[DEBUG] ReviewerApp.run() returned plan with {len(result.actions)} actions."
            )
        return result
