from typing import Optional, Sequence
from textual.widgets import Tree
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.domain.models.plan import Plan


class TuiDriver:
    """
    Driver for the ReviewerApp (TUI) to support simulated interactions in tests.
    """

    def __init__(self, plan: Plan, system_env, file_system):
        self.app = ReviewerApp(
            plan=plan, system_env=system_env, file_system=file_system
        )

    async def run_interaction(self, keys: Sequence[str]) -> Optional[Plan]:
        """
        Runs the app and simulates the provided keypresses.
        """
        async with self.app.run_test() as pilot:
            # Ensure the Tree has focus
            pilot.app.query_one(Tree).focus()
            for key in keys:
                await pilot.press(key)
                await pilot.pause()
            return self.app.plan
