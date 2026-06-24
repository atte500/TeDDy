from typing import Protocol


from typing import Optional


class IEnvironmentInspector(Protocol):
    """
    Outbound Port for inspecting the user's environment (OS, terminal, etc.).
    """

    def get_environment_info(self) -> dict[str, str]:
        """
        Gathers key information about the system environment.

        Returns:
            dict[str, str]: A dictionary of environment properties.
            Keys include: os_name, os_version, python_version, cwd, shell,
            current_date (YYYY-MM-DD), current_time (HH:MM:SS).
        """
        ...

    def get_git_status(self) -> Optional[str]:
        """
        Gathers the current Git status of the working directory (short format).

        Returns:
            Optional[str]: The output of 'git status -s' or None if not a git repo.
        """
        ...

    def get_full_git_status(self) -> Optional[str]:
        """
        Gathers the full Git status of the working directory (including branch info).

        Returns:
            Optional[str]: The output of 'git status' or None if not a git repo.
        """
        ...
