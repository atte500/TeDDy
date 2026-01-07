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
