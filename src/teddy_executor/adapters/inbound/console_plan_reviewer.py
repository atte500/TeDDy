from typing import Optional, TYPE_CHECKING
from teddy_executor.core.ports.inbound.plan_reviewer import IPlanReviewer

if TYPE_CHECKING:
    from teddy_executor.core.domain.models.plan import Plan, ActionData
    from teddy_executor.core.ports.outbound import (
        IUserInteractor,
        IFileSystemManager,
        IConfigService,
    )
    from teddy_executor.core.ports.inbound.edit_simulator import IEditSimulator


from teddy_executor.core.services.action_changeset_builder import ActionChangeSetBuilder


class ConsolePlanReviewer(IPlanReviewer):
    """
    Inbound adapter for reviewing plans via the standard console (sequential Y/N).
    """

    def __init__(
        self,
        user_interactor: "IUserInteractor",
        file_system_manager: "IFileSystemManager",
        config_service: "IConfigService",
        edit_simulator: "IEditSimulator",
    ):
        self._user_interactor = user_interactor
        self._changeset_builder = ActionChangeSetBuilder(
            file_system_manager, config_service, edit_simulator
        )

    def review(self, plan: "Plan") -> Optional["Plan"]:
        """
        Legacy review method. Delegating to review_plan for bulk console review.
        """
        return self.review_plan(plan)

    def review_plan(self, plan: "Plan") -> Optional["Plan"]:
        """
        Initiates a bulk interactive review process for the entire plan.
        """
        if self._user_interactor.confirm_plan_review(plan):
            return plan
        return None

    def review_action(
        self,
        action: "ActionData",
        total_actions: int,
        agent_name: Optional[str] = None,
    ) -> bool:
        prompt = ActionChangeSetBuilder.format_action_prompt(action)

        change_set = self._changeset_builder.create_change_set(action)

        approved, _ = self._user_interactor.confirm_action(
            action=action, action_prompt=prompt, change_set=change_set
        )
        action.selected = approved
        return approved
