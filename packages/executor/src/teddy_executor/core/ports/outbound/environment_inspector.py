from typing import Protocol


class IEnvironmentInspector(Protocol):
    """
    Outbound Port for inspecting the user's environment (OS, terminal, etc.).
    """

    def get_environment_info(self) -> dict[str, str]:
        """
        Gathers key information about the system environment.

        Returns:
            dict[str, str]: A dictionary of environment properties.
        """
        ...
