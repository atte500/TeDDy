import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from teddy_executor.core.services.action_executor import ActionExecutor
from teddy_executor.core.domain.models import ActionLog


class PrototypeActionExecutor(ActionExecutor):
    """Prototype with updated isolation reason."""

    def _check_action_isolation(
        self,
        action,
        total_actions: int,
        interactive: bool = False,
        skip_isolation: bool = False,
    ) -> ActionLog | None:
        """
        Ensures terminal actions are handled correctly with the NEW reason.
        """
        if skip_isolation:
            return None

        # Terminal actions include INVOKE, PROMPT, RETURN
        if action.is_terminal and total_actions > 1 and not interactive:
            return self._handle_skipped_action(
                action,
                "Automatically skipped: This action must be performed in isolation.",
            )

        return None
