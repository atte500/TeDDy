from typing import Protocol


from typing import Optional, Protocol


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

    def get_git_status(self) -> Optional[str]:
        """
        Gathers the current Git status of the working directory.

        Returns:
            Optional[str]: The output of 'git status -s' or None if not a git repo.
        """
        ...
