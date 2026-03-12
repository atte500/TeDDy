from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from teddy_executor.core.domain.models import ActionData, ChangeSet


class IUserInteractor(ABC):
    @abstractmethod
    def prompt(self, text: str, default: str = "") -> str:
        """
        Prompts the user for input and returns the response.

        Args:
            text: The prompt text to display.
            default: The default value if the user provides no input.

        Returns:
            The user's response as a string.
        """
        pass

    @abstractmethod
    def ask_question(self, prompt: str, resources: list[str] | None = None) -> str:
        """
        Asks the user a question and returns their free-text response.

        Args:
            prompt: The question to display to the user.
            resources: Optional list of reference files to display.

        Returns:
            The user's response as a string.
        """
        pass

    @abstractmethod
    def display_message(self, message: str) -> None:
        """
        Displays an informational message to the user.

        Args:
            message: The message to display.
        """
        pass

    @abstractmethod
    def confirm_action(
        self,
        action: "ActionData",
        action_prompt: str,
        change_set: Optional["ChangeSet"] = None,
    ) -> tuple[bool, str]:
        """
        Displays a prompt describing an action and asks the user for y/n confirmation.
        If the user denies the action, it prompts them for an optional reason.

        Args:
            action: The Action object to be confirmed.
            action_prompt: A non-empty string describing the action to be confirmed.
            change_set: An optional ChangeSet representing the proposed changes for preview.

        Returns:
            A tuple containing:
            - bool: True if the user approved, False otherwise.
            - str: The user's reason for denial, or an empty string.
        """
        pass

    @abstractmethod
    def notify_skipped_action(self, action: "ActionData", reason: str) -> None:
        """
        Notifies the user that an action was skipped.

        Args:
            action: The Action that was skipped.
            reason: The reason the action was skipped.
        """
        pass

    @abstractmethod
    def confirm_manual_handoff(
        self,
        action_type: str,
        target_agent: str | None,
        resources: list[str],
        message: str,
    ) -> tuple[bool, str]:
        """
        Displays a handoff request and asks for confirmation.
        An empty response means approval. Any text is a rejection reason.

        Returns:
            A tuple of (approved: bool, rejection_reason: str)
        """
        pass
