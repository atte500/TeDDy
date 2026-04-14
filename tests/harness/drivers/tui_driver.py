from typing import Optional, Sequence
from textual.widgets import Tree
from teddy_executor.adapters.inbound.textual_plan_reviewer import ReviewerApp
from teddy_executor.core.domain.models.plan import Plan


class TuiDriver:
    """
    Driver for the ReviewerApp (TUI) to support simulated interactions in tests.
    """

    def __init__(self, plan: Plan, system_env, file_system, console_tooling=None):
        from unittest.mock import MagicMock

        self.app = ReviewerApp(
            plan=plan,
            system_env=system_env,
            file_system=file_system,
            console_tooling=console_tooling or MagicMock(),
            action_dispatcher=MagicMock(),
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
                # If a worker is running (e.g. action_preview), we must not block
                # but we should allow it to reach its first await (e.g. push_screen_wait).
                await pilot.pause()

                # If the current screen is a modal, wait for workers isn't
                # possible as they are blocked on the screen's dismissal.
                # Only wait for workers if we are on the main screen.
                if pilot.app.screen == pilot.app._screen_stack[0]:
                    await pilot.app.workers.wait_for_complete()
                    await pilot.pause()

            return self.app.plan

    async def set_input(self, pilot, selector: str, value: str):
        """
        Sets the value of an Input widget directly and submits it.
        This is significantly faster than pilot.press(*chars).
        """
        from textual.widgets import Input

        # Use app.screen to ensure we target the active (possibly modal) screen
        target = pilot.app.screen.query_one(selector, Input)
        target.value = value
        await pilot.press("enter")
        # Allow dismissal/callback processing
        await pilot.pause()
