from abc import ABC, abstractmethod
from typing import Dict, Optional, Sequence


class IPlanningUseCase(ABC):
    """
    Defines the contract for generating an AI plan.
    """

    @abstractmethod
    def generate_plan(
        self,
        user_message: str,
        turn_dir: str,
        context_files: Optional[Dict[str, Sequence[str]]] = None,
    ) -> tuple[str, float]:
        """
        Generates a new plan.md file based on context and user message.

        Args:
            user_message: The instructions from the user.
            turn_dir: The directory where artifacts for the turn are stored.
            context_files: Optional scoped context files to include.

        Returns:
            The path to the generated plan.md.
        """
        pass
