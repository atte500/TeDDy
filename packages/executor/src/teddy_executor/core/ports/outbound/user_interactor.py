from abc import ABC, abstractmethod


class UserInteractor(ABC):
    @abstractmethod
    def ask_question(self, prompt: str) -> str:
        """
        Asks the user a question and returns their free-text response.

        Args:
            prompt: The question to display to the user.

        Returns:
            The user's response as a string.
        """
        pass

    @abstractmethod
    def confirm_action(self, action_prompt: str) -> tuple[bool, str]:
        """
        Displays a prompt describing an action and asks the user for y/n confirmation.
        If the user denies the action, it prompts them for an optional reason.

        Args:
            action_prompt: A non-empty string describing the action to be confirmed.

        Returns:
            A tuple containing:
            - bool: True if the user approved, False otherwise.
            - str: The user's reason for denial, or an empty string.
        """
        pass
