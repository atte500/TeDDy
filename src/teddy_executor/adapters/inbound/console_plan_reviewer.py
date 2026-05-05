from __future__ import annotations
from typing import Optional, TYPE_CHECKING
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer
from teddy_executor.core.domain.models.project_context import ProjectContext

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import (
        Plan,
        ActionData,
    )
    from teddy_executor.core.ports.outbound import (
        IUserInteractor,
        IFileSystemManager,
        IConfigService,
    )
    from teddy_executor.core.ports.inbound.edit_simulator import (
        IEditSimulator,
    )


from teddy_executor.core.services.action_changeset_builder import ActionChangeSetBuilder


class ConsolePlanReviewer(IPlanReviewer):
    """
    Inbound adapter for reviewing plans via the standard console (sequential Y/N).
    """

    def __init__(
        self,
        user_interactor: IUserInteractor,
        file_system_manager: IFileSystemManager,
        config_service: IConfigService,
        edit_simulator: IEditSimulator,
    ):
        self._user_interactor = user_interactor
        self._changeset_builder = ActionChangeSetBuilder(
            file_system_manager, config_service, edit_simulator
        )

    def review(
        self, plan: "Plan", project_context: Optional["ProjectContext"] = None
    ) -> Optional["Plan"]:
        """
        Prints the plan header and returns immediately to proceed to actions.
        """
        _ = project_context
        import typer

        header = f'\n▶ Reviewing Plan: "{plan.title}"'
        typer.secho(header, fg=typer.colors.CYAN, bold=True, err=True)
        return plan

    def review_action(
        self,
        action: "ActionData",
        total_actions: int,
        agent_name: Optional[str] = None,
    ) -> tuple[bool, str]:
        _ = total_actions
        _ = agent_name
        prompt = ActionChangeSetBuilder.format_action_prompt(action)

        change_set = self._changeset_builder.create_change_set(action)

        approved, message = self._user_interactor.confirm_action(
            action=action, action_prompt=prompt, change_set=change_set
        )
        action.selected = approved
        return approved, message
